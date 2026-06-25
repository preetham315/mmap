# Exploration playbook

Loaded on demand during `mmap`'s analysis step. Goal: explore an arbitrary, unfamiliar, or large repo **efficiently** and ground every claim in real `path:line` evidence so it can become a mind-map spec.

**Evidence-first rule.** Prefer opening the actual code over guessing. Every fact you emit carries:

- `evidence`: array of `path:line` you can point to.
- `confidence` 0..1 mapped to a color (bands match the default thresholds high=0.75, medium=0.45; see `spec-schema.md`):
  - **GREEN (0.75–1.0)** — you opened the cited file and it _directly_ shows the claim.
  - **AMBER (0.45–0.74)** — inferred from naming/convention/structure, OR relayed by a subagent the main thread did not re-open.
  - **RED (0.0–0.44)** — guessed/unverified, or a placeholder for unmapped scope.

Naming-only inference is **never GREEN** — AI-generated code lies about itself with confident names. Open the file to go green.

---

## 1. Universal exploration discipline

Order of operations for ANY repo. Do not deep-read until the breadth pass is done.

1. **Breadth-first map (cheap, high-signal).** Do not read implementation yet.
   - Run `scripts/repo_map.py --root <repo>` FIRST — it gives the stack, dir tree, entry-point
     candidates, and per-file signatures in one compact read (~95%+ fewer tokens than reading
     files). See `token-efficiency.md`. This replaces most manual breadth-pass reading.
   - Then read only root manifests, `README*`, `ARCHITECTURE*`, `docs/` index, `CLAUDE.md` for intent.
   - Note the directory shape — top-level dirs are your first subsystem hypothesis.
2. **Derive 3–8 top-level subsystems** (§3). Cap at 8 for readability; fold the rest into "other".
3. **Find true entry points** — not the first file alphabetically. main()/CLI bootstrap, server startup, route registration, the exported public API (package `main`/`exports`, `lib.rs`, `__init__.py`). §2 gives per-stack locations.
4. **Trace ONE representative path end-to-end** (e.g. one HTTP request → handler → service → data layer → response). Reading one spine beats skimming everything.
5. **Collect `path:line` for every claim** as you go, and tag green (opened it) vs amber (inferred). Re-open anything important before promoting to green.

Quick budget check: if `git ls-files | wc -l` is large (>~1500) or you find a monorepo, jump to §4 (fan out) and §6 (budget tactics) before reading deeply.

---

## 2. Per-stack playbooks

Detect the stack from manifests/files, then open the "first files" before anything else.

### Node / TypeScript

|                     |                                                                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Detect**          | `package.json`, `tsconfig.json`, `pnpm-lock.yaml`/`yarn.lock`/`package-lock.json`                                                                                   |
| **Entry points**    | `package.json` `main`/`module`/`exports`/`bin`/`scripts.start`; `src/index.ts`, `src/main.ts`, `server.ts`                                                          |
| **Routes/handlers** | Express/Fastify: `app.use`/`router.*` in `src/routes/`, `routes/`. Nest: `*.controller.ts`, `@Controller`. Next: `pages/api/`, `app/**/route.ts`, `app/**/page.tsx` |
| **Layering**        | `src/` → `controllers`/`routes`, `services`, `repositories`/`models`, `lib`/`utils`                                                                                 |
| **Config/DI**       | `.env`, `config/`, Nest modules (`*.module.ts`, providers), `tsconfig.json` `paths` (alias map → real layout)                                                       |
| **Open first**      | `package.json`, `tsconfig.json`, entry file, route registration, one controller→service chain                                                                       |

### Python

|                     |                                                                                                                   |
| ------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Detect**          | `pyproject.toml`, `requirements*.txt`, `setup.py`/`setup.cfg`, `Pipfile`                                          |
| **Entry points**    | `manage.py` (Django), `asgi.py`/`wsgi.py`, `main.py`, `app.py`, `[project.scripts]`/`console_scripts`             |
| **Routes/handlers** | Django: `urls.py` + `views.py`. Flask: `@app.route`/blueprints. FastAPI: `APIRouter`, `@app.get/post`, `routers/` |
| **Layering**        | apps/packages, `views`/`routers` → `services` → `models`/`repositories`; Django `models.py`, `serializers.py`     |
| **Config/DI**       | Django `settings.py`, `.env`, `pyproject.toml` deps, FastAPI `Depends()`                                          |
| **Open first**      | manifest, entry (`manage.py`/`main.py`), top-level URL/router include, one view/endpoint→model                    |

### Go

|                     |                                                                                                            |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Detect**          | `go.mod` (module path + deps), `go.sum`                                                                    |
| **Entry points**    | `cmd/<name>/main.go`, root `main.go` (`package main`, `func main`)                                         |
| **Routes/handlers** | `net/http` `http.HandleFunc`/`ServeMux`; chi/gin/echo router setup, `handler`/`api` packages               |
| **Layering**        | `cmd/` (binaries), `internal/` (private), `pkg/` (public libs); `internal/<domain>/{service,repo,handler}` |
| **Config/DI**       | env/flags, `config` package, wire/fx if present, struct constructors (`NewX`)                              |
| **Open first**      | `go.mod`, `cmd/*/main.go`, router setup, one handler→service→repo                                          |

### Rust

|                     |                                                                                               |
| ------------------- | --------------------------------------------------------------------------------------------- |
| **Detect**          | `Cargo.toml` (`[workspace]` → multi-crate), `Cargo.lock`                                      |
| **Entry points**    | `src/main.rs` (bin `fn main`), `src/lib.rs` (lib API), `src/bin/*.rs`                         |
| **Routes/handlers** | axum `Router::new().route(...)`, actix `App::new().service(...)`; `routes`/`handlers` modules |
| **Layering**        | `mod`/`pub mod` tree from `lib.rs`/`main.rs`; workspace members as subsystems                 |
| **Config/DI**       | `Cargo.toml` features/deps, `config`/`settings`, builder structs, `state` passed to handlers  |
| **Open first**      | `Cargo.toml` (workspace members), `main.rs`/`lib.rs` module tree, router, one handler chain   |

### Java / Kotlin

|                     |                                                                                               |
| ------------------- | --------------------------------------------------------------------------------------------- |
| **Detect**          | `pom.xml` (Maven) or `build.gradle[.kts]` (Gradle); `src/main/java`/`kotlin`                  |
| **Entry points**    | `@SpringBootApplication` class with `main`; `Application.java`/`*Application.kt`              |
| **Routes/handlers** | `@RestController`/`@Controller`, `@RequestMapping`/`@GetMapping`                              |
| **Layering**        | `controller` → `service` → `repository` (`@Repository`/Spring Data) → `entity`/`model`        |
| **Config/DI**       | `application.yml`/`.properties`, `@Configuration`/`@Bean`, `@Autowired`/constructor injection |
| **Open first**      | build file, `*Application`, one controller→service→repository, `application.yml`              |

### Ruby

|                     |                                                                              |
| ------------------- | ---------------------------------------------------------------------------- |
| **Detect**          | `Gemfile`, `config.ru`, `Rakefile`, `app/` + `config/` (Rails)               |
| **Entry points**    | `config/routes.rb`, `config/application.rb`, `config.ru`                     |
| **Routes/handlers** | `config/routes.rb` → `app/controllers/*_controller.rb` actions               |
| **Layering**        | MVC: `app/controllers`, `app/models`, `app/services`/`app/jobs`, `app/views` |
| **Config/DI**       | `config/environments/*`, `config/initializers/`, `Gemfile`                   |
| **Open first**      | `Gemfile`, `config/routes.rb`, one controller→model                          |

### .NET / C#

|                     |                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------ |
| **Detect**          | `*.csproj`, `*.sln`, `Program.cs`                                                          |
| **Entry points**    | `Program.cs` (minimal hosting / `Main`), `Startup.cs` (older)                              |
| **Routes/handlers** | `[ApiController]` `Controllers/`, attribute routing `[HttpGet]`; minimal `app.MapGet(...)` |
| **Layering**        | `Controllers` → `Services` → `Repositories`/`Data` (EF `DbContext`); `Models`/`DTOs`       |
| **Config/DI**       | `appsettings.json`, `builder.Services.Add*` in `Program.cs`, `IServiceCollection`          |
| **Open first**      | `*.csproj`, `Program.cs` (DI + pipeline), one controller→service                           |

### PHP

|                     |                                                                                                     |
| ------------------- | --------------------------------------------------------------------------------------------------- |
| **Detect**          | `composer.json`; Laravel `artisan` + `app/`; Symfony `bin/console` + `src/`                         |
| **Entry points**    | `public/index.php`; Laravel `routes/web.php`/`routes/api.php`; Symfony `config/routes.yaml`         |
| **Routes/handlers** | Laravel `routes/*.php` → `app/Http/Controllers`; Symfony `#[Route]` controllers in `src/Controller` |
| **Layering**        | Controllers → Services/Actions → Models (Eloquent) / Repositories (Doctrine)                        |
| **Config/DI**       | `.env`, `config/`, Laravel service providers, Symfony `services.yaml`                               |
| **Open first**      | `composer.json`, route file, one controller→model                                                   |

### Frontend SPA (React / Vue / Svelte / Angular)

|                  |                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| **Detect**       | `package.json` deps: `react`/`vue`/`svelte`/`@angular/core`; `vite.config`/`next.config`/`angular.json` |
| **Entry points** | `src/main.tsx`/`main.ts`, `src/App.*`, `index.html`; Angular `main.ts` + `AppModule`                    |
| **Routing**      | `react-router` `<Routes>`, Vue Router `routes`, SvelteKit `src/routes/`, Angular `RouterModule.forRoot` |
| **State**        | Redux/Zustand/Jotai stores, Pinia/Vuex, Svelte stores, NgRx; `store/`, `state/`, `*.slice.ts`           |
| **API clients**  | `api/`, `services/`, `lib/api`, generated SDK; `fetch`/`axios`/`react-query`/`apollo`                   |
| **Open first**   | `package.json`, entry + root component, router config, one store, one API client                        |

---

## 3. Subsystem heuristics

Carve into **3–8 subsystems**. Signals, in order of trust:

1. **Workspace boundaries** (highest signal — explicit). Detect monorepos:
   - npm/yarn/pnpm: `package.json` `workspaces`, `pnpm-workspace.yaml`
   - tooling: `lerna.json`, `nx.json`, `turbo.json`
   - Rust: `[workspace] members` in `Cargo.toml`
   - Go: multiple `go.mod` files
   - Each workspace package = a candidate subsystem.
2. **Top-level dirs** that map to roles (`api/`, `web/`, `worker/`, `services/<x>`, `cmd/<x>`, `packages/<x>`, `apps/<x>`).
3. **Domain folders** under `src/` (`auth/`, `billing/`, `orders/`) — group by business capability, not by tech layer.
4. **Manifest deps** — a heavy framework (Django, Spring, Rails) implies its conventional layout is a subsystem skeleton.

**"One subsystem" vs internal detail:** a subsystem owns a distinct responsibility AND a clear boundary (separate package, deployable, or domain folder with its own entry/API). `utils/`, `types/`, a single helper file, or a sub-folder reached only through its parent's public API → internal detail, not a top-level node. If two folders only ever import each other, they are one subsystem. When >8 candidates, merge the smallest/most-coupled and consider fanning out (§4).

---

## 4. Parallel-subagent brief

When the repo is large (>~1500 tracked files, >8 subsystems, or a monorepo), SKILL.md fans out **one READ-ONLY exploration subagent per subsystem** via the Task tool, all dispatched in a **single message**. Fill this template per subsystem:

```
You are a READ-ONLY exploration subagent for the `mmap` skill. Do NOT modify, create,
or delete any file. Run no build/test/format commands.

Subsystem: <name>
Root path(s): <dir(s)>
Repo root: <abs path>

Investigate ONLY this subsystem and report a tight bullet list (~25 lines MAX):
- One-line responsibility (what it owns).
- Public entry points / exported API, each with `path:line`.
- What it IMPORTS from sibling subsystems (name + `path:line` of the import).
- What imports IT (callers), with `path:line` if found.
- Notable external dependencies (frameworks/libs it leans on).
- Any design decision it embodies (e.g. ORM vs raw SQL, queue vs sync, custom vs library) — cite the revealing `path:line`.
- Obvious risks: coupling hotspots, missing tests, code that looks AI-generated.

RULES:
- For EVERY claim, include a `path:line` you actually OPENED. No path:line = drop the claim.
- Do not infer behavior from a name alone; open the file or label it "(inferred)".
- Prefer grep to locate, then open only the spine files fully. Stay within your root path(s).
- Keep it to ~25 lines. Bullets, not prose.
```

**After fan-out:** every subagent-relayed claim is **AMBER** until the main thread re-opens the spine files itself. Re-open the 2–4 most load-bearing files per subsystem (entry point, the cross-subsystem import, the decision-revealing file) to promote to GREEN. Cross-subsystem edges are most error-prone — verify those imports directly.

---

## 5. Mode-specific exploration focus

### `architecture`

Hunt for, then map:

- **Entry points** — every binary/server/CLI/public API (`path:line`).
- **Module decomposition** — the 3–8 subsystems (§3) and one-line responsibilities.
- **Layering / boundaries** — controller→service→data (or its absence); which layers exist, which are skipped.
- **Primary data-flow path** — trace one request/job end-to-end; this becomes the spine `question→answer` chain.
- **Key external deps** — framework, DB/ORM, queue, cache, auth provider.
- **Considerations** (note nodes) — coupling hotspots (god modules, circular imports), test gaps, areas that look high-AI-churn (inconsistent style, dead code, over-abstracted, misleading names).
- **Craftsmanship to spotlight** — as you read, notice the _good_ parts too: a genuinely clever algorithm, an elegant abstraction, an unusually efficient path. Mark those nodes `highlight` (gold ⭐) with a one-line reason + `evidence`. The map should celebrate wins, not only flag risks. Use sparingly — only real standouts.

### `decisions`

Each decision is a `question` node; the **chosen** path is the `primary` answer, rejected paths are dashed alternatives. Hunt these fingerprints — **each must cite the revealing code**:
| Decision | Look for |
|---|---|
| ORM vs raw SQL | ORM models/`@Entity` vs `db.query("SELECT ...")`/query builder |
| Monolith vs services | single app vs `services/*` + RPC/HTTP clients between them |
| Sync vs queue/async | direct calls vs `enqueue`/Celery/BullMQ/SQS/Kafka producers |
| REST vs GraphQL vs RPC | route handlers vs `schema.graphql`/resolvers vs gRPC `.proto`/tRPC |
| Custom vs library | hand-rolled util vs a dependency in the manifest |
| Global state vs DI | singletons/module globals vs constructor/container injection |
| Auth strategy | sessions vs JWT vs OAuth provider; middleware/guards location |
| Error handling | central handler/Result type vs scattered try/catch |
| Config strategy | env vars vs config files vs secrets manager |

### `topic` (free-text)

1. Grep the seed terms (and synonyms) across the repo to find anchor files.
2. Trace the ONE flow the topic names, end-to-end, opening each hop.
3. Branch points (if/strategy/feature flags) become **dashed alternative** answer siblings.
4. Stop at the topic's edges — don't map the whole repo.

---

## 6. Large-repo / token-budget tactics

- **Never read everything.** The breadth pass is `tree` + manifests + READMEs only.
- **Cap subsystems at ~8**; fold the long tail into one "other" group node.
- **Cap node counts** — a readable mind map is dozens of nodes, not hundreds. Prefer one representative example over exhaustive enumeration.
- **Prefer grep over full-file reads** to _locate_ (find the symbol/route/import); then open only the **spine files** fully.
- **Throttle reads** — read the entry point, the one cross-boundary import, and the decision file per subsystem; skip the rest.
- **If still too big:** scope to the **top-N subsystems** by importance, and emit a single **RED** "not yet mapped" node covering the remainder (with the dir list), so the gap is explicit rather than hidden.
- For monorepos, fan out (§4) instead of serially reading; it parallelizes and keeps tool output out of the main thread's context.

---

## 7. Edge cases

- **Empty repo** — no tracked files or only config. Emit a single note node saying so; don't fabricate structure.
- **Non-code repo** (docs/data/config only) — map the content/dir structure as the subsystems; skip entry-point hunting; lower confidence on "behavior" claims.
- **No git** — use Glob (`**/*`) instead of `git ls-files`; manually skip vendored dirs (next bullet).
- **Skip generated/vendored dirs** — `node_modules`, `dist`, `build`, `out`, `target`, `.venv`/`venv`, `vendor`, `.next`, `coverage`, `*.min.js`, lockfiles, `__pycache__`. They inflate file counts and contain no design intent.
- **AI-generated code with MISLEADING names** — a function named `validateUser` may do nothing of the sort. Naming/convention inference stays **AMBER, never GREEN**. Promote to GREEN only after opening the file and confirming the body matches the claim. When the body contradicts the name, that contradiction is itself a high-value note node.
