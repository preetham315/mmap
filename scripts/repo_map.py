#!/usr/bin/env python3
"""repo_map.py — emit a COMPACT structural skeleton of a repo so the mmap skill can
reason over architecture without reading dozens of files into the model context.

It is the cheap "structure-first" pass: detect the stack, list the tree, and extract
per-file SIGNATURES (functions/classes/routes — declarations, not bodies) with regex.
Read this once, then open only the few spine files fully.

Stdlib only (Python 3.9+). Deterministic. No network.

Usage:
  repo_map.py [--root DIR] [--dir SUBDIR] [--max-files N] [--max-sigs-per-file K]
              [--max-output-chars C] [--full]
"""
import argparse, os, re, subprocess, sys
from pathlib import Path

SKIP_DIRS = {
    "node_modules", "dist", "build", "out", "target", "vendor", ".git", ".hg", ".svn",
    ".venv", "venv", "env", "__pycache__", ".next", ".nuxt", ".svelte-kit", "coverage",
    ".mypy_cache", ".pytest_cache", ".gradle", ".idea", ".vscode", "bin", "obj",
    ".terraform", "Pods", "DerivedData", ".cache", ".turbo", ".parcel-cache", "site-packages",
}
SKIP_SUFFIX = (".min.js", ".min.css", ".map", ".lock", ".snap", ".woff", ".woff2", ".ttf",
               ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf", ".zip", ".gz",
               ".mp3", ".mp4", ".wasm", ".so", ".dylib", ".dll", ".class", ".pyc")
MANIFESTS = {
    "package.json": "node/js-ts", "tsconfig.json": "typescript", "pyproject.toml": "python",
    "requirements.txt": "python", "setup.py": "python", "go.mod": "go", "Cargo.toml": "rust",
    "pom.xml": "java(maven)", "build.gradle": "jvm(gradle)", "build.gradle.kts": "kotlin(gradle)",
    "Gemfile": "ruby", "composer.json": "php", "pubspec.yaml": "dart/flutter",
}
ENTRY_HINTS = ("main.go", "main.rs", "lib.rs", "main.py", "app.py", "manage.py", "asgi.py",
               "wsgi.py", "index.ts", "index.js", "main.ts", "server.ts", "server.js",
               "Program.cs", "Startup.cs", "config.ru", "artisan", "index.php")

# language -> list of (compiled regex, short-label). Match declarations/routes only.
def _c(*p): return [(re.compile(rx), lbl) for rx, lbl in p]
LANG = {
    ".py": _c((r"^\s*(?:async\s+)?def\s+\w+\s*\(", "def"), (r"^\s*class\s+\w+", "class"),
              (r"^\s*@(?:app|router|blueprint)\.(?:route|get|post|put|delete|patch)", "route")),
    ".ts": _c((r"^\s*export\s+(?:default\s+)?(?:async\s+)?function\s+\w+", "fn"),
              (r"^\s*export\s+(?:abstract\s+)?class\s+\w+", "class"),
              (r"^\s*export\s+(?:const|interface|type|enum)\s+\w+", "export"),
              (r"\.(?:get|post|put|delete|patch|use)\s*\(\s*['\"`]/", "route"),
              (r"^\s*@(?:Controller|Get|Post|Put|Delete|Injectable|Module)\b", "decorator")),
    ".go": _c((r"^func\s+(?:\([^)]*\)\s+)?\w+\s*\(", "func"),
              (r"^type\s+\w+\s+(?:struct|interface)\b", "type"),
              (r"\.(?:HandleFunc|Handle|GET|POST|PUT|DELETE)\s*\(", "route")),
    ".rs": _c((r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+\w+", "fn"),
              (r"^\s*(?:pub\s+)?(?:struct|enum|trait)\s+\w+", "type"),
              (r"^\s*(?:pub\s+)?mod\s+\w+", "mod"),
              (r"\.route\s*\(\s*['\"]/", "route")),
    ".java": _c((r"^\s*(?:public|private|protected).*\b\w+\s*\([^)]*\)\s*\{?\s*$", "method"),
                (r"^\s*(?:public|abstract|final)?\s*(?:class|interface|enum)\s+\w+", "type"),
                (r"^\s*@(?:RestController|Controller|GetMapping|PostMapping|RequestMapping|Service|Repository|SpringBootApplication)\b", "spring")),
    ".cs": _c((r"^\s*(?:public|private|protected|internal).*\b\w+\s*\([^)]*\)", "method"),
              (r"^\s*(?:public|abstract|sealed)?\s*(?:class|interface|record|struct)\s+\w+", "type"),
              (r"^\s*\[(?:ApiController|HttpGet|HttpPost|Route)\b", "attr")),
    ".rb": _c((r"^\s*def\s+\w+", "def"), (r"^\s*(?:class|module)\s+\w+", "type"),
              (r"^\s*(?:get|post|put|delete|patch|resources?)\s+['\":]", "route")),
    ".php": _c((r"^\s*(?:public|private|protected)?\s*function\s+\w+", "fn"),
               (r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+\w+", "type"),
               (r"Route::(?:get|post|put|delete|patch)\s*\(", "route"),
               (r"^\s*#\[Route\b", "attr")),
}
LANG[".tsx"] = LANG[".ts"]; LANG[".js"] = LANG[".ts"]; LANG[".jsx"] = LANG[".ts"]
LANG[".mjs"] = LANG[".ts"]; LANG[".kt"] = LANG[".java"]; LANG[".kts"] = LANG[".java"]
CODE_EXT = set(LANG.keys())


def list_files(root):
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True,
                             text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            return [root / p for p in out.stdout.splitlines()]
    except Exception:
        pass
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            files.append(Path(dp) / fn)
    return files


def keep(p):
    if any(part in SKIP_DIRS for part in p.parts):
        return False
    return not p.name.endswith(SKIP_SUFFIX)


def extract_sigs(path, patterns, max_sigs, max_bytes=180_000):
    sigs = []
    try:
        if path.stat().st_size > max_bytes:
            return sigs, 0
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return sigs, 0
    lines = text.splitlines()
    for i, ln in enumerate(lines, 1):
        if len(ln) > 400:        # likely minified/data
            continue
        for rx, lbl in patterns:
            if rx.search(ln):
                sigs.append((i, lbl, ln.strip()[:120]))
                break
        if len(sigs) >= max_sigs:
            break
    return sigs, len(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--dir", default=None, help="restrict to a subdirectory")
    ap.add_argument("--max-files", type=int, default=600, help="max files to show signatures for")
    ap.add_argument("--max-sigs-per-file", type=int, default=10)
    ap.add_argument("--max-output-chars", type=int, default=60000)
    ap.add_argument("--full", action="store_true", help="no per-file signature cap")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    scope = (root / args.dir).resolve() if args.dir else root
    files = [p for p in list_files(root) if keep(p)]
    if args.dir:
        files = [p for p in files if str(p).startswith(str(scope))]

    # stack + entry points
    names = {p.name for p in files}
    stacks = sorted({lbl for m, lbl in MANIFESTS.items() if m in names})
    entries = sorted({str(p.relative_to(root)) for p in files if p.name in ENTRY_HINTS})

    code = [p for p in files if p.suffix in CODE_EXT]
    # directory file counts
    dir_counts = {}
    for p in files:
        rel = p.relative_to(root)
        d = str(rel.parent) if str(rel.parent) != "." else "."
        dir_counts[d] = dir_counts.get(d, 0) + 1

    total_loc = 0
    per_file = []  # (relpath, loc, sigs)
    cap = (10**9) if args.full else args.max_sigs_per_file
    for p in sorted(code):
        sigs, loc = extract_sigs(p, LANG[p.suffix], cap)
        total_loc += loc
        if sigs:
            per_file.append((str(p.relative_to(root)), loc, sigs))

    # ---- emit ----
    o = []
    o.append(f"# REPO MAP  root={root}")
    o.append(f"# files={len(files)}  code={len(code)}  with-signatures={len(per_file)}  loc~{total_loc}")
    o.append(f"# stack: {', '.join(stacks) or 'unknown'}")
    if entries:
        o.append(f"# entry-point candidates: {', '.join(entries[:12])}")
    o.append("")
    o.append("## TREE (dir: file-count)")
    for d in sorted(dir_counts):
        depth = 0 if d == "." else d.count(os.sep) + 1
        if depth > 4:
            continue
        o.append(f"{'  '*depth}{('.' if d=='.' else os.path.basename(d))}/ ({dir_counts[d]})")
    o.append("")
    o.append("## SIGNATURES (path · LOC · declarations)")

    shown, truncated = 0, 0
    body = []
    for rel, loc, sigs in sorted(per_file, key=lambda x: -len(x[2])):
        if shown >= args.max_files:
            truncated = len(per_file) - shown
            break
        body.append(f"{rel} ({loc} LOC)")
        for i, lbl, txt in sigs:
            body.append(f"  L{i} [{lbl}] {txt}")
        shown += 1

    out = "\n".join(o) + "\n" + "\n".join(body)
    if truncated:
        out += f"\n[+{truncated} more files with signatures not shown — narrow with --dir <subdir>]"
    if len(out) > args.max_output_chars:
        out = out[:args.max_output_chars] + f"\n[output truncated at {args.max_output_chars} chars — use --dir to scope]"
    print(out)


if __name__ == "__main__":
    main()
