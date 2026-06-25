---
name: mmap
version: "1.0.0"
description: "Generate an interactive hand-drawn mind map of the current codebase. Maps the architecture, the design decisions, or a specific feature/flow you name; grounds every claim in real path:line evidence; color-codes each claim by how verified it is; and opens a self-contained offline HTML map with expand/collapse, pan/zoom, drag, search, and PNG/SVG export. Built for brownfield / AI-generated projects that are hard to follow."
argument-hint: "architecture | decisions | the auth flow | (no arg = pick interactively)"
allowed-tools: Bash, Read, Write, Glob, Grep, AskUserQuestion, Task
author: preethamvreddy
license: MIT
user-invocable: true
metadata:
  openclaw:
    emoji: "🗺️"
    requires:
      env: []
      optionalEnv: []
      bins:
        - python3
    files:
      - "scripts/*"
      - "assets/*"
      - "references/*"
    tags:
      - codebase
      - architecture
      - mind-map
      - mindmap
      - visualization
      - onboarding
      - brownfield
      - code-comprehension
      - diagram
      - decisions
      - data-flow
      - hand-drawn
      - offline
      - interactive
      - ai-skill
      - clawhub
---

# mmap — interactive hand-drawn codebase mind map

Analyze the **current project** and render an interactive, hand-drawn (Excalidraw-style)
mind map: questions in sketchy ovals, dashed lines to answers, alternatives in
confidence-colored dashed lines, a grouped cluster of considerations, plus
expand/collapse, pan/zoom, drag, search, and PNG/SVG export. The map is a single
self-contained **offline** HTML file. Built to make AI-generated / brownfield code
followable: it shows _what the code does_ and _how sure we are_, grounded in real
`path:line` evidence and color-coded by confidence.

Modes, chosen by the argument after `/mmap`:

- **`architecture`** — whole-system overview (entry points, modules, layering, data flow, key deps).
- **`decisions`** — the design decisions the code embodies, the alternatives, a recommendation each.
- **`tech`** (a.k.a. `stack`) — technology usage across the repo: languages, frameworks, libraries,
  datastores, infra — and _where_ each is used.
- **`data`** (a.k.a. `datamodel` / `schema`) — the data model: key entities/tables and how they relate.
- **`onboarding`** (a.k.a. `start` / `tour`) — a newcomer's guide: how to run it, the first files to
  read, the domain glossary.
- **`deps`** (a.k.a. `dependencies`) — the internal module dependency graph: what imports what,
  coupling hotspots, and any cycles.
- **`risks`** (a.k.a. `health`) — code health: test gaps, TODO/FIXME/HACK debt, complexity/churn
  hotspots, and AI-smelling areas (dead code, over-abstraction, misleading names).
- **`api`** (a.k.a. `endpoints` / `routes`) — the public surface: HTTP routes / CLI commands /
  exported API, what each does, and its auth/inputs.
- **`glossary`** (a.k.a. `terms`) — the domain vocabulary: the recurring terms/concepts and where
  each is defined.
- **`flows`** (a.k.a. `all flows`) — auto-discover the major functional flows and map **each**, bundled
  into **one HTML with a flow navigator** (◀ ▶ + dropdown + arrow keys).
- **`<free text>`** (e.g. `the auth flow`) — trace one feature/flow end to end.
- **no argument** — ask the user which one (Step 1a).

**Bundles (multiple maps in one file):** any run can emit a _bundle_ — several maps in one
self-contained HTML with a navigator. `flows` always does. The user can also ask for "everything in
one file" (e.g. architecture + decisions + data + key flows) → emit a bundle. See Step 3/4.

---

## Runtime preflight

Run this once, in a single Bash block, before anything else. It resolves Python,
validates the skill files, finds the project root, and prepares the output dir.

```bash
# 1) Python 3.9+ (renderer is stdlib-only; do NOT require 3.12)
for py in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  command -v "$py" >/dev/null 2>&1 || continue
  "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)' || continue
  MMAP_PYTHON="$py"; break
done
[ -z "${MMAP_PYTHON:-}" ] && { echo "ERROR: mmap needs Python 3.9+." >&2; exit 1; }

# 2) SKILL_DIR = absolute path of the directory containing THIS SKILL.md you just Read.
#    Substitute the path your harness reported. scripts/ and assets/ are always its
#    direct children. Examples:
#      Read ~/.claude/skills/mmap/SKILL.md  → SKILL_DIR=$HOME/.claude/skills/mmap
SKILL_DIR="<absolute path of the directory containing the SKILL.md you Read>"
if [ ! -f "$SKILL_DIR/scripts/render_mindmap.py" ] || [ ! -f "$SKILL_DIR/assets/template.html" ]; then
  echo "ERROR: render_mindmap.py / template.html not found under SKILL_DIR=$SKILL_DIR" >&2
  exit 1
fi

# 3) project root + output dir
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
OUT_DIR="$PROJECT_ROOT/.mindmap"; mkdir -p "$OUT_DIR" 2>/dev/null || OUT_DIR="$(mktemp -d)"
echo "MMAP_PYTHON=$MMAP_PYTHON  SKILL_DIR=$SKILL_DIR  OUT_DIR=$OUT_DIR"

# 4) cheap stack detection (one pass; do NOT deep-crawl yet)
ls -1 "$PROJECT_ROOT" 2>/dev/null | grep -iE \
  'package\.json|pyproject\.toml|requirements.*\.txt|setup\.py|go\.mod|Cargo\.toml|pom\.xml|build\.gradle|Gemfile|composer\.json|.*\.csproj|pubspec\.yaml' \
  || echo "(no obvious manifest at root — inspect subdirs / monorepo)"
```

---

## Step 1 — Parse the argument & choose the mode

`$ARGUMENTS` is the text after `/mmap`, trimmed. Look at the **first word** (lowercased); if it's a
known mode keyword, that's the MODE and the **rest is optional scope** (a target repo/dir/sub-area):

- `architecture` / `arch` → **architecture**
- `decisions` / `decision` / `tradeoffs` → **decisions**
- `tech` / `stack` / `technology` / `technologies` → **tech**
- `data` / `datamodel` / `schema` / `model` → **data**
- `onboarding` / `start` / `tour` / `getting-started` → **onboarding**
- `deps` / `dependencies` → **deps**
- `risks` / `health` / `smells` → **risks**
- `api` / `endpoints` / `routes` → **api**
- `glossary` / `terms` / `vocab` → **glossary**
- `flows` / `all-flows` (or "all flows") → **flows** (always a bundle)
- empty / whitespace → **Step 1a** (ask)
- anything else → **topic**, with `TOPIC` = the full argument text (keep its casing)

Trailing words after a mode keyword are **scope**, not a topic: `/mmap decisions ./services/api` =
decisions mode scoped to that path; `/mmap flows the billing module` = flows mode scoped to billing.
But a phrase that doesn't _start_ with a mode keyword is a topic: `/mmap the architecture of billing`
is a topic trace, not architecture mode. If the user names a target repo/path (e.g.
`decisions ../other-repo`) and you're not already inside it, set `PROJECT_ROOT` to that path.

The user may also ask for **everything / all maps in one file** → emit a **bundle** of
{architecture, decisions, data, key flows} (Step 3).

### Step 1a — No argument: ask

Call **AskUserQuestion** (single-select):

- Question: "What kind of mind map do you want for this codebase?" · Header: "Map type"
- Options:
  1. **Architecture** — "Whole-system overview as a story: structure, the core guarantee, the cracks."
  2. **All flows (one file)** — "Auto-discover the major functional flows; navigate between them in one HTML."
  3. **Tech / data / decisions** — "Tech stack usage, the data model, or the key design decisions (I'll confirm which)."
  4. **A specific topic** — "Trace one feature or flow. I'll ask which."

The free-text "Other" box doubles as a direct mode or topic ("data model", "onboarding", "the auth
flow"). If a choice needs narrowing (3 or 4), ask one short follow-up, then set MODE.

---

## Step 2 — Analyze the codebase (evidence-first, **token-lean**)

This is the expensive step on brownfield repos. **Spend tokens on structure first, file
bodies last.** Read `references/exploration.md` and `references/token-efficiency.md`. Protocol,
cheapest path first:

0. **(Optional) Use a code-index MCP if one is connected.** Run `ToolSearch` for a codebase
   index/memory tool (e.g. `codebase-memory`, `claude-context`, `code-memory`, `search_code`).
   If present, query it for structure + relevant snippets instead of reading files (cite the
   `path:line` it returns). This is by far the cheapest path. If absent, continue below.
1. **Structure-first skeleton (do this BEFORE reading files).** Run the bundled extractor:
   ```bash
   "$MMAP_PYTHON" "$SKILL_DIR/scripts/repo_map.py" --root "$PROJECT_ROOT"   # add --dir <sub> to scope
   ```
   It prints the stack, the dir tree, entry-point candidates, and per-file **signatures**
   (declarations/routes — not bodies). One compact read replaces dozens of file reads
   (~95%+ fewer tokens). Reason over this to pick the **spine**.
2. **Read only the spine, minimally.** Open just the handful of load-bearing files
   (entry point, the cross-boundary import, the decision-revealing file). Prefer `Grep` to
   locate and `Read` with an `offset`/`limit` over whole-file reads. Don't read what the
   skeleton already told you.
3. **Derive 3–8 subsystems.** Cap for readability.
4. **Large repo?** If `>~1500` files, `>8` subsystems, or a monorepo: **fan out one READ-ONLY
   `Task` subagent per subsystem in a single message** (brief in `exploration.md §4`). Give
   each the relevant `repo_map.py --dir <subsystem>` slice so it doesn't re-scan. Subagents
   keep bulk file content out of the main thread's context.
5. **Verify the spine yourself.** Whatever you mark `primary:true`, the **main thread reads
   those files itself** — skeleton- and subagent-derived claims are amber-grade until re-opened.
6. **Cache across runs.** Reuse a prior `$OUT_DIR/<mode-slug>.spec.json` if present: only
   re-analyze subsystems whose files changed (compare against the repo_map), keep the rest.

**Tell a STORY (read `references/story-arc.md`).** The map is a narrative told through its
questions, not a flat Q&A. The **solid spine is a chain of questions** (`question → question`,
each `parent` = the previous question) that build on each other; **answers hang off each question
as dashed, confidence-colored branches** (one `primary:true` lead + alternatives). The renderer
draws this automatically. Rules: an **adaptive opening question** that hooks _this_ repo (never a
canned template); pick a lens (crux / artifact / onboarding) and a protagonist; **inherit a noun
each beat** so the questions read as prose; make the **climax** (the payoff beat) your strongest,
gold-starred, verified-green node; let color **darken honestly** toward the cracks; cluster the
falling action into a collapsed "Considerations" group.

Mode focus (full detail in `exploration.md §5` and `story-arc.md`):

- **architecture** — usually the **crux lens**: open on the one guarantee the architecture bends
  around (or, if none, an onboarding hook), then chain questions through the happy path → the
  threat → how it's enforced (climax) → the cost → the first file to open at 3am. Star the clever
  bits; end with a "Considerations" group.
- **decisions** — each beat is a decision-question; the choice the code made is the `primary`
  dashed answer (cited), alternatives are dashed siblings, the recommendation is a `note`.
- **topic** — the **artifact lens**: chain questions that follow the one flow end to end (intent →
  transforms → guarantees → output → where it leaks); branch points become dashed alternatives.
- **tech** — source the truth from manifests (`package.json`, `pyproject.toml`, `go.mod`, …) + a
  grep of imports. Spine: what's the stack & why → what each layer leans on (web/runtime, data/ORM,
  queue/cache, auth, build/CI, infra) → where a dependency is load-bearing or risky (pinned
  submodule, heavy/abandoned dep, version skew). Each tech node cites the manifest line + a use site.
- **data** — the data model. Source from migrations/ORM models/schema files. Spine: what are the core
  entities → how they relate (FKs / associations) → the invariants/constraints that protect them →
  where the model is awkward (god table, missing index, denormalization). Use a `group` per bounded
  context; cite the model/migration `path:line`.
- **onboarding** — the **onboarding lens** for a newcomer. Spine: what is this & why does it exist →
  how do I run it (entry point + `make`/scripts + env) → the 5 files to read first → the domain
  glossary (terms that recur) → what will bite me (gotchas). End with "first PR-sized task" ideas.
- **flows** — **discover the flows first**, then map each as its own topic-story, and emit a
  **bundle**. Find flows from: route/handler tables, CLI subcommands, job/worker entry points, UI
  pages/actions, public API methods. Cap at ~6–10 flows (most important first; note any omitted).
  Each map in the bundle = one flow (artifact lens). Give each a clear `title` (the flow name) — that
  title is what shows in the navigator.
- **deps** — the internal module dependency graph (not third-party libs — that's `tech`). Source from
  import statements (`grep` imports per module). Spine: what's the dependency backbone → which
  modules are depended-on-most (the core) vs leaf → coupling hotspots (a util everything imports) →
  any **import cycles** (call these out as red). Group low-level shared modules. Cite an import
  `path:line` per edge claim.
- **risks** — code health, honestly. Sources: test layout vs source (coverage gaps), `grep`
  TODO/FIXME/HACK/XXX, large files / long functions (complexity), and AI-smells (dead code,
  over-abstraction, copy-paste, names that lie). Spine: where is this most likely to break → the
  biggest gaps (untested critical path) → the debt markers → the smelliest areas. Be fair: confidence
  reflects what you actually saw; don't invent risks. End with a "quick wins" note.
- **api** — the public surface. Sources: route registrations, controller/handler decorators, CLI
  command definitions, exported package API. Spine: what's the surface shape → the main resource
  groups (a `group` per resource/router) → auth & input validation → the risky/unauthenticated
  endpoints. Each endpoint node cites its handler `path:line`; note method + path.
- **glossary** — the domain vocabulary. Find recurring domain nouns (entity/type names, ubiquitous
  terms in names & docs). Spine: the core domain concept → the terms that orbit it → easily-confused
  pairs → terms that are overloaded/ambiguous in the code. Each term cites where it's defined
  (the class/type/constant `path:line`). Keep definitions one line; this map is a lookup, so a
  shallow, wide shape (one question, many term answers, grouped) is fine.

---

## Step 3 — Build the mind-map spec

Author a **flat list of nodes** per `references/spec-schema.md` (read it for all fields,
node types, and worked examples). Shape:

```json
{
  "mode": "architecture",
  "title": "Architecture — <repo name>",
  "project_root": "<PROJECT_ROOT>",
  "generated_at": "<ISO-8601>",
  "thresholds": { "high": 0.75, "medium": 0.45 },
  "nodes": [
    {
      "id": "q1",
      "type": "question",
      "text": "The one thing it can't get wrong is X — where does the code make its stand?"
    },
    {
      "id": "a1",
      "type": "answer",
      "parent": "q1",
      "primary": true,
      "confidence": 0.85,
      "text": "Layered modular monolith; the guarantee lives in the service layer",
      "evidence": ["src/services/index.ts:8", "src/api/routes.ts:1"]
    },
    {
      "id": "a1b",
      "type": "answer",
      "parent": "q1",
      "confidence": 0.5,
      "text": "Rival framing to resist: it's just a CRUD API",
      "evidence": ["src/features/"]
    },
    {
      "id": "q2",
      "type": "question",
      "parent": "q1",
      "text": "Given that stand — walk me through one real request, end to end"
    },
    {
      "id": "a2",
      "type": "answer",
      "parent": "q2",
      "primary": true,
      "confidence": 0.85,
      "text": "router -> controller -> service -> repo -> Postgres",
      "evidence": ["src/api/routes.ts:1", "src/db/repo.ts:12"]
    },
    {
      "id": "g1",
      "type": "group",
      "parent": "q2",
      "text": "Considerations",
      "options": [
        {
          "id": "o1",
          "text": "utils imported everywhere (coupling)",
          "confidence": 0.8,
          "evidence": ["src/utils/index.ts:1"]
        }
      ]
    }
  ]
}
```

The spine here is `q1 → q2` (solid, the story); answers and the group hang off each question (dashed).

**Rules (enforced — see spec-schema.md):**

- Node types: `question` (oval) · `answer` (oval child of a question) · `group` (box of `option`s) ·
  `option` (lives in a group's `options`) · `note` (caveat/recommendation).
- **Solid spine = the question chain** (`question → question`, each `parent` = the previous
  question); **answers are always dashed** off their question, confidence-colored. Mark **one
  `primary:true` lead answer per question** (heavier dash); the rest are dashed alternatives.
- One `confidence` (0..1) per claim-bearing node → drives its (dashed) edge color. **You emit
  confidence, never colors.**
- Every `answer`/`option`/`note` that asserts something about the code carries non-empty `evidence`
  of `path:line`. Evidence-free nodes only for pure question/framing text.
- **Spotlight craftsmanship:** when you find a genuinely clever / elegant / notably efficient
  implementation (a neat algorithm, an elegant abstraction, an unusually efficient path), mark that
  node `"highlight": {"kind":"clever|elegant|efficient", "reason":"one line why"}` — it gets a gold
  ⭐. Use sparingly (only real standouts) and back the reason with `evidence` you actually read.
- Readability: ≤6–7 sibling answers per question, ≤8 options per group; push detail into `note`s;
  set `collapsed:true` on deep/auxiliary subtrees.

### Confidence rubric (condensed — full version + examples in spec-schema.md)

Confidence = _how verified is this against the actual code_, not _how good the idea is_.

- 🟢 **0.75–1.0 verified** — you opened the cited `path:line` in the **main thread** and it directly shows the claim.
- 🟡 **0.45–0.74 inferred** — from naming/convention/structure, or relayed by a subagent you didn't re-open.
- 🔴 **0.0–0.44 uncertain** — guessed, contradicted, or couldn't locate the code.

Guards: **no evidence ⇒ cannot be green** (cap ≤0.5). **Subagent-relayed = amber until re-verified.**
Conflicting cites ⇒ red + a `note`. Misleading names stay amber (open the file to go green).
**Pre-write self-check:** scan the spec — downgrade any green backed only by a filename or an
unopened subagent line. One unjustified green poisons the whole map's credibility.

### Bundles — several maps in one HTML (`flows`, or "everything in one file")

For `flows` or any multi-map request, emit a **bundle** instead of a single spec: a top-level
`maps` array, each entry being a normal map (`title`, `mode`, optional `thresholds`/`palette`, and
its own flat `nodes`). The renderer adds a navigator (◀ ▶ + dropdown + ← → keys); each map's
`title` is its navigator label.

```json
{
  "bundle": true,
  "title": "<repo> — all flows",
  "maps": [
    {
      "mode": "topic",
      "title": "Auth flow",
      "nodes": [
        /* a story spine + answers */
      ]
    },
    {
      "mode": "topic",
      "title": "Checkout flow",
      "nodes": [
        /* … */
      ]
    },
    {
      "mode": "topic",
      "title": "Webhook intake",
      "nodes": [
        /* … */
      ]
    }
  ]
}
```

Each map follows all the rules above (question spine, dashed answers, evidence, confidence, stars).
Order the maps most-important-first. For "everything in one file," mix modes (e.g. an `architecture`
map, a `data` map, then the top flows).

---

## Step 4 — Write the spec

Pick a slug matching the mode (`architecture`, `decisions`, `tech`, `data`, `onboarding`, `deps`,
`risks`, `api`, `glossary`, `flows` for a bundle) or `topic-<slug>` (lowercase the topic,
`[^a-z0-9]+`→`-`, trim, ≤60 chars). Write the JSON with the **Write tool** (no shell escaping):

`$OUT_DIR/<slug>.spec.json`

---

## Step 5 — Render

```bash
SLUG="<mode-slug>"; TITLE="<map title>"
"$MMAP_PYTHON" "$SKILL_DIR/scripts/render_mindmap.py" \
  --spec "$OUT_DIR/$SLUG.spec.json" \
  --out  "$OUT_DIR/$SLUG.html" \
  --mode "$MODE" --title "$TITLE" --open
```

Check the exit code. On non-zero, surface stderr and DO NOT claim success. The script
writes the HTML even if opening a browser fails; if it didn't open, give the manual command:

- macOS: `open "$OUT_DIR/$SLUG.html"` · Linux: `xdg-open …` · WSL: `wslview …` (or `explorer.exe "$(wslpath -w …)"`).

---

## Step 6 — Report (terse)

- `🗺️ Mind map → $OUT_DIR/<slug>.html` (opened, or the manual-open command).
- Legend: 🟢 verified in code · 🟡 inferred from structure · 🔴 uncertain. Solid = primary path, dashed = alternative.
- Interactions: click a node = expand/collapse · scroll = zoom · drag background = pan · drag node = move · search box · SVG/PNG export.
- `Spec JSON at $OUT_DIR/<slug>.spec.json — re-run /mmap <mode> to regenerate, or hand-edit the JSON and re-render.`
- **Honesty note when red nodes exist:** e.g. "3 of 18 nodes are red — I couldn't verify the worker-queue wiring; point me at it and I'll redo that branch."
- If `.git` exists and `.mindmap/` isn't ignored (`git check-ignore -q .mindmap`), suggest once:
  "Tip: add `.mindmap/` to .gitignore (or commit the maps as living docs — your call)." Do **not** auto-edit `.gitignore`.

---

## Edge cases

| Case                      | Do this                                                                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Empty / no source         | Don't fabricate. Say the repo looks empty; offer to point at a subdir.                                                                |
| Non-code repo (docs/data) | Map the content/dir structure; lower confidence on behavior claims; ask before inventing architecture.                                |
| Huge repo > token budget  | Breadth-only reads + capped subagent fan-out; cap subsystems ~8 and node counts; emit one 🔴 "not yet mapped" node for the remainder. |
| Monorepo                  | Each workspace package = a subsystem; top level is the package dependency graph; per-package detail in collapsed groups.              |
| No git                    | `PROJECT_ROOT=$(pwd)`; enumerate with Glob; skip the gitignore tip.                                                                   |
| `.mindmap/` not writable  | Preflight already falls back to `mktemp -d`; report that path.                                                                        |
| Topic not found           | Grep empty → tell the user, list closest matches, ask to repick. Don't map guesses.                                                   |
| Renderer/template missing | Preflight hard-errors with the path. Don't half-run.                                                                                  |
| Special chars in topic    | Written into JSON via the Write tool and slugified for filenames — never interpolated raw into Bash.                                  |
