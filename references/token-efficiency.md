# Token efficiency

Analyzing a brownfield repo is the expensive part of `mmap`. The skill is **token-lean by
default with zero dependencies**, and can **optionally** plug into external accelerators when
they're available. Never make an accelerator a hard requirement — the skill must keep working
on any repo with only `python3`.

## The default lean protocol (no dependencies)

Ordered cheapest-first; this is what SKILL.md Step 2 enforces.

1. **Structure before bodies.** `scripts/repo_map.py` extracts a compact skeleton — stack,
   directory tree, entry points, and per-file **signatures** (function/class/route
   _declarations_, not bodies) via regex. Measured on an 80-file Python repo: **~8.6k tokens
   for the full skeleton vs ~241k tokens to read every file — ~97% fewer.** Read it once, then
   decide what to open.
   ```bash
   python3 scripts/repo_map.py --root <repo>            # whole repo skeleton
   python3 scripts/repo_map.py --root <repo> --dir api  # scope to one subsystem
   ```
2. **Grep to locate, read minimally.** Use `Grep` to find the symbol/route/import, then `Read`
   with `offset`/`limit` — never cat whole files you already understand from the skeleton.
3. **Read only the spine fully.** The 2–4 load-bearing files per subsystem (entry point, the
   cross-boundary import, the decision-revealing file). Everything else stays at signature level.
4. **Fan out subagents for big repos.** One READ-ONLY `Task` subagent per subsystem keeps that
   subsystem's file content in the subagent's context, not the main thread's — the main thread
   only sees terse summaries. Pass each the `repo_map.py --dir <subsystem>` slice.
5. **Cap output.** ≤8 subsystems, dozens of nodes (not hundreds); one 🔴 "not yet mapped" node
   for any remainder rather than exhaustively reading the long tail.
6. **Cache across runs.** Keep `$OUT_DIR/<mode>.spec.json`; on re-run, diff the new `repo_map`
   against the old map and only re-analyze subsystems whose signatures changed.

## Optional accelerators (auto-detected; graceful fallback)

### A code-index / "codebase memory" MCP

If one is connected, SKILL.md Step 2.0 detects it (via `ToolSearch`) and queries it for
structure and relevant snippets instead of reading files — typically the cheapest path of all.
Use the `path:line` it returns as evidence; still re-open the spine files in the main thread to
promote a claim to 🟢 green.

| MCP                                                                    | What it does                                                                                             | Notes                           |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------- |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Tree-sitter + LSP + semantic vector knowledge graph, 158 langs; ~99% fewer tokens for structural queries | single static binary, zero deps |
| [claude-context](https://github.com/zilliztech/claude-context)         | Hybrid semantic code search MCP for Claude Code                                                          | needs an embedding provider     |
| [code-memory](https://github.com/kapillamba4/code-memory)              | Local vector search + git history, **fully offline**                                                     | no external API                 |

To enable: install one and add it to your MCP config. `mmap` will pick it up automatically;
without it, the lean protocol above is used.

### Headroom (environment-level compression)

[Headroom](https://github.com/chopratejas/headroom) (Apache-2.0) compresses tool outputs,
files, and RAG chunks _before_ they reach the model — **60–95% fewer tokens, AST-aware,
reversible** (the model can call `headroom_retrieve` for the original). It wraps Claude Code
transparently as a **proxy** (point the SDK base URL at `localhost:8787`) or as an **MCP**, so
it cuts `mmap`'s token use with **no changes to this skill**. This is the best whole-session
lever; the skill simply benefits when it's running. See the Headroom README for setup.

## Rule of thumb

Most token spend on a brownfield repo is _re-reading code you didn't need_. The skeleton +
grep-to-locate + spine-only reading removes ~90%+ of that on its own; the MCP and Headroom
remove most of what's left. Reach for them in that order: **skeleton → grep → spine → subagents
→ (MCP) → (Headroom)**.
