# mmap spec schema — the contract

This is the contract between the analysis step (which authors a spec) and
`scripts/render_mindmap.py` (which renders it). Author a **flat list of nodes**;
the render script normalizes it into the nested tree the HTML template consumes,
validates it, and inlines it. Write the spec with the **Write tool** (clean JSON,
no shell escaping).

---

## Top-level shape

```jsonc
{
  "version": 1,                       // optional, informational
  "mode": "architecture",             // architecture | decisions | topic  (shown in toolbar)
  "title": "Architecture — <repo>",   // shown as the map title
  "project_root": "/abs/path",        // optional; basename shown in toolbar
  "generated_at": "2026-06-23T14:30:00Z",  // optional ISO-8601
  "thresholds": { "high": 0.75, "medium": 0.45 },  // optional; color band cutoffs
  "palette": { ... },                 // optional; override colors (rarely needed)
  "nodes": [ /* flat list, see below */ ]
}
```

Only `nodes` is strictly required. Everything else has sensible defaults.

### Bundle shape (several maps in one HTML)

To put multiple maps in one self-contained file (the `flows` mode, or "everything in one file"),
use a bundle instead: a top-level `maps` array of normal map specs. The renderer shows a navigator
(◀ ▶ buttons + a dropdown + ← → arrow keys); each map's `title` is its navigator label.

```jsonc
{
  "bundle": true,                       // optional flag; presence of `maps` is what matters
  "title": "acme — all flows",          // bundle title (browser tab)
  "maps": [
    { "mode": "topic", "title": "Auth flow",    "thresholds": {…}, "nodes": [ … ] },
    { "mode": "topic", "title": "Checkout flow", "nodes": [ … ] }
  ]
}
```

Each entry in `maps` is exactly a single-map spec (its own `title`, `mode`, optional
`thresholds`/`palette`, and flat `nodes`). `render_mindmap.py` normalizes each one; per-map
`thresholds`/`palette` default if omitted. All node rules below apply per map.

---

## Node object (flat list)

```jsonc
{
  "id": "a1", // string, unique. Defaults to n<index> if omitted.
  "type": "answer", // question | answer | group | option | note
  "text": "Layered: handlers -> services -> repositories",
  "parent": "q1", // id of the parent node. Omit/null for a root.
  "primary": true, // marks THIS node's incoming edge as the solid spine
  "confidence": 0.9, // 0..1, drives edge color (see rubric). Omit for pure questions.
  "evidence": ["src/api/routes.ts:1", "src/services/user.ts:14"], // path:line refs
  "detail": "Optional longer text shown in the hover tooltip.",
  "collapsed": false, // start collapsed (hides this node's subtree)
  "highlight": { "kind": "clever", "reason": "why this is noteworthy" }, // optional ⭐, see below

  // ONLY for type:"group" — the cluster's option ovals, rendered stacked inside the box:
  "options": [
    {
      "id": "o1",
      "text": "Monolith vs Modular",
      "confidence": 0.9,
      "evidence": ["Cargo.toml:1"],
    },
  ],
}
```

### Node types

| type       | renders as                          | use for                                                                         |
| ---------- | ----------------------------------- | ------------------------------------------------------------------------------- |
| `question` | bold oval                           | a question being asked of the codebase (usually a root or a hinge)              |
| `answer`   | oval, confidence-tinted             | an answer to its parent question; `primary` = the choice the code actually made |
| `group`    | rounded rectangle holding `options` | a cluster of related considerations/options shown together                      |
| `option`   | small oval **inside** a `group`     | one item in a group (lives in the parent group's `options`, NOT the flat list)  |
| `note`     | small rounded rect                  | a caveat, recommendation, or aside attached to any node                         |

### Edges (derived, not authored) — the story spine

Edge style is driven by the **child's type**, so the map reads as a story (see `story-arc.md`):

- **`question → question`** → **SOLID, thick, neutral dark** — this is the narrative spine. Chain
  the questions: each spine question's `parent` is the **previous question**.
- **`question → answer | group | note`** → **DASHED, confidence-colored** (green ≥ high, amber ≥
  medium, red < medium). A `primary:true` lead answer gets a slightly heavier dash; alternatives
  are lighter. `primary` no longer controls solid/dashed — the question chain is the only solid.
- **color** of a dashed edge = the child's `confidence` through `thresholds`.

### Roots

Nodes with no `parent` (or a `parent` that doesn't resolve) are roots. With one root it becomes the tree root; with several, the renderer wraps them under a synthesized question root titled with `title`.

### Highlighting noteworthy code (`highlight`)

Independent of confidence (which is about _verification_), `highlight` calls out a genuinely
**clever, elegant, or notably efficient** implementation — the "this is a wonderful idea" moments
worth celebrating. A highlighted node/option gets a **gold ⭐ + a gold halo**, its reason shows in
the tooltip, and the toolbar **★ Spotlight** button dims everything except highlighted nodes.

```jsonc
"highlight": { "kind": "clever", "reason": "Single regex pass extracts all signatures — O(n), no AST" }
// shorthands also accepted:  "highlight": true   |   "highlight": "the reason string"
```

- `kind` ∈ `clever` | `elegant` | `efficient` (label only; all render the gold star).
- `reason` — one line on _why_ it's noteworthy. Cite it with `evidence` like any other claim.
- Works on `answer`, `note`, `group`, and `option` nodes.
- **Use sparingly** — only real standouts (a neat algorithm, an elegant abstraction, a notably
  efficient path). Starring everything makes nothing stand out. A highlight is a claim too:
  back it with evidence you actually read.

---

## Confidence rubric (so the colors are trustworthy)

`confidence` answers ONE question: **how sure are we this reflects the actual code, and on what basis?** It is NOT "how good is this idea." Assign it from what you actually did, not from plausibility.

| Band             | Range     | Meaning                                                                                                 | Required basis                                               |
| ---------------- | --------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 🟢 **verified**  | 0.75–1.0  | You opened the cited code and it directly shows the claim                                               | ≥1 real `path:line` you actually read in the **main thread** |
| 🟡 **inferred**  | 0.45–0.74 | Rests on naming/dir conventions/framework defaults, or a subagent report you did not personally re-open | a path (file/dir) but body not confirmed first-hand          |
| 🔴 **uncertain** | 0.0–0.44  | Plausible but unverified, contradicted, or about code you couldn't locate                               | weak/indirect or no evidence                                 |

Within a band: literal-code-at-that-line → 0.9–1.0; faithful one-step summary → 0.75–0.89; strong convention but not every hop traced → 0.6–0.74; naming-only inference → 0.45–0.59; educated guess from ecosystem priors → 0.25–0.44; speculation → < 0.25 (prefer to omit or label "unknown").

### Hard guards

- **Evidence gates the band.** No `evidence` ⇒ cannot be 🟢. Cap evidence-free claims at amber ≤ 0.5, and only for framing-level statements.
- **Subagent-relayed = amber until re-verified.** A claim from a fan-out subagent the main thread didn't re-open stays ≤ 0.74. To go green, the main thread reads the file itself (or the subagent quoted the exact line and you spot-checked the spine).
- **Conflict ⇒ red + note.** If two cites disagree, drop to red and add a `note` explaining the conflict.
- **Misleading names stay amber.** AI-generated code often has names that lie. Inference from a name alone is amber, never green.
- **Pre-write self-check.** Before writing the spec, scan it: any 🟢 node backed only by a filename (no line) or an unopened subagent line? Downgrade it. One unjustified green poisons the whole map's credibility — honesty over coverage.

### Worked examples

- 🟢 0.95 — "Routes are registered in `app.use(router)`" · evidence `src/server.ts:42` (you read line 42; it's literally that call).
- 🟢 0.8 — "Auth is JWT via middleware" · evidence `src/mw/auth.ts:10` (read it; `jwt.verify(...)` present).
- 🟡 0.6 — "`/workers` handles async jobs" · evidence `src/workers/` (dir + names imply it; you didn't open the bodies).
- 🟡 0.5 — "Repository pattern for DB access" · evidence `src/repo/userRepo.ts` (filename convention; class body unread).
- 🔴 0.35 — "Probably uses a work-stealing pool" · no evidence (ecosystem guess).
- 🔴 0.2 — "May call a third-party billing API" · couldn't find any matching code.

---

## Readability rules

- ≤ 6–7 sibling answers per question; ≤ 8 options per group.
- Prefer one `group` over ten loose nodes. Push secondary detail into `note`s.
- Set `collapsed:true` on deep/auxiliary subtrees so the first view stays legible — the user expands what they want.
- Keep `text` short (it wraps inside an oval); put the long version in `detail`.

---

## Sample specs (one per mode)

### architecture

```json
{
  "mode": "architecture",
  "title": "Architecture — acme-api",
  "thresholds": { "high": 0.75, "medium": 0.45 },
  "nodes": [
    {
      "id": "q1",
      "type": "question",
      "text": "What is the best way to represent the current architecture?"
    },
    {
      "id": "a1",
      "type": "answer",
      "parent": "q1",
      "primary": true,
      "confidence": 0.9,
      "text": "Layered modular monolith: handlers -> services -> repositories",
      "evidence": [
        "src/api/routes.ts:1",
        "src/services/index.ts:8",
        "src/db/repo.ts:12"
      ]
    },
    {
      "id": "a2",
      "type": "answer",
      "parent": "q1",
      "confidence": 0.5,
      "text": "Could be framed feature-first (vertical slices)",
      "evidence": ["src/features/"]
    },
    {
      "id": "g1",
      "type": "group",
      "parent": "q1",
      "text": "Considerations",
      "options": [
        {
          "id": "o1",
          "text": "Coupling hotspot: utils imported everywhere",
          "confidence": 0.8,
          "evidence": ["src/utils/index.ts:1"]
        },
        {
          "id": "o2",
          "text": "No tests under src/workers",
          "confidence": 0.7,
          "evidence": ["src/workers/"]
        }
      ]
    },
    {
      "id": "q2",
      "type": "question",
      "parent": "a1",
      "text": "How does a request flow end to end?"
    },
    {
      "id": "a3",
      "type": "answer",
      "parent": "q2",
      "primary": true,
      "confidence": 0.78,
      "text": "Router -> controller -> service -> repo -> Postgres",
      "evidence": ["src/api/routes.ts:1", "src/db/repo.ts:12"]
    }
  ]
}
```

### decisions

```json
{
  "mode": "decisions",
  "title": "Decisions — acme-api",
  "nodes": [
    { "id": "d1", "type": "question", "text": "How is persistence handled?" },
    {
      "id": "d1a",
      "type": "answer",
      "parent": "d1",
      "primary": true,
      "confidence": 0.9,
      "text": "Hand-written SQL via a thin repository layer",
      "evidence": ["src/db/repo.ts:1", "src/db/queries.sql:1"]
    },
    {
      "id": "d1b",
      "type": "answer",
      "parent": "d1",
      "confidence": 0.5,
      "text": "Alternative: an ORM (Prisma/TypeORM) — not used here",
      "evidence": ["package.json:20"]
    },
    {
      "id": "d1n",
      "type": "note",
      "parent": "d1a",
      "confidence": 0.7,
      "text": "Recommendation: fine at this scale; revisit if query sprawl grows",
      "evidence": ["src/db/queries.sql:1"]
    }
  ]
}
```

### topic (e.g. `/mmap the auth flow`)

```json
{
  "mode": "topic",
  "title": "Auth flow — acme-api",
  "nodes": [
    { "id": "t1", "type": "question", "text": "How does the auth flow work?" },
    {
      "id": "t2",
      "type": "answer",
      "parent": "t1",
      "primary": true,
      "confidence": 0.88,
      "text": "POST /login -> verify password -> issue JWT",
      "evidence": ["src/api/auth.ts:14", "src/services/auth.ts:30"]
    },
    {
      "id": "t3",
      "type": "answer",
      "parent": "t2",
      "primary": true,
      "confidence": 0.82,
      "text": "JWT checked by middleware on protected routes",
      "evidence": ["src/mw/requireAuth.ts:8"]
    },
    {
      "id": "t4",
      "type": "answer",
      "parent": "t2",
      "confidence": 0.4,
      "text": "OAuth path may exist but I couldn't confirm it",
      "evidence": []
    }
  ]
}
```

---

## Render CLI

```
python3 scripts/render_mindmap.py --spec <spec.json> --out <map.html> [--open] [--title T] [--mode M]
```

The script validates, normalizes flat→nested, inlines libs+font+data into `assets/template.html`, writes a single self-contained offline HTML, and (with `--open`) opens it. It prints spec warnings (e.g. a green node with no evidence) to stderr — fix those for a trustworthy map.
