#!/usr/bin/env python3
"""render_mindmap.py — turn a flat mind-map spec into a self-contained, offline,
interactive hand-drawn HTML map and (optionally) open it in the browser.

Stdlib only (Python 3.9+). The heavy renderer lives in ../assets/template.html;
this script validates the spec, normalizes the flat node list into the nested tree
the template consumes, inlines the vendored libraries + font, injects the data, and
writes one self-contained file.

Usage:
  render_mindmap.py --spec spec.json --out map.html [--open] [--title T] [--mode M]
"""
import argparse, base64, json, os, sys, re, webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
VENDOR = ASSETS / "vendor"
TEMPLATE = ASSETS / "template.html"

VALID_TYPES = {"question", "answer", "group", "option", "note"}
DEFAULT_THRESHOLDS = {"high": 0.75, "medium": 0.45}


def warn(msg):
    print(f"  ! {msg}", file=sys.stderr)


def die(msg, code=1):
    print(f"render_mindmap: error: {msg}", file=sys.stderr)
    sys.exit(code)


def coerce_conf(v):
    if v is None:
        return None
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


def _clean_highlight(h):
    """Pass a node's highlight through: True | "reason" | {kind, reason} -> normalized or None."""
    if not h:
        return None
    if h is True:
        return {"kind": "clever", "reason": ""}
    if isinstance(h, str):
        return {"kind": "clever", "reason": h}
    if isinstance(h, dict):
        return {"kind": str(h.get("kind", "clever")), "reason": str(h.get("reason", ""))}
    return None


def normalize(spec, arg_title, arg_mode):
    """Flat {nodes:[...]} authored spec -> nested tree the template expects."""
    nodes = spec.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        die("spec has no 'nodes' array (or it is empty)")

    # 1. index + shallow validation
    by_id, warnings = {}, 0
    clean = []
    seen = set()
    for i, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            warn(f"node #{i} is not an object — skipped"); warnings += 1; continue
        nid = str(raw.get("id") or f"n{i}")
        if nid in seen:
            nid = f"{nid}__dup{i}"; warn(f"duplicate id at #{i} -> renamed {nid}"); warnings += 1
        seen.add(nid)
        ntype = raw.get("type", "answer")
        if ntype not in VALID_TYPES:
            warn(f"node {nid}: unknown type '{ntype}' -> treated as 'answer'"); warnings += 1
            ntype = "answer"
        n = {
            "id": nid,
            "type": ntype,
            "text": str(raw.get("text", raw.get("label", ""))).strip(),
            "parent": raw.get("parent"),
            "primary": bool(raw.get("primary", False)),
            "confidence": coerce_conf(raw.get("confidence")),
            "evidence": [str(e) for e in (raw.get("evidence") or []) if str(e).strip()],
            "detail": (str(raw["detail"]).strip() if raw.get("detail") else None),
            "collapsed": bool(raw.get("collapsed", False)),
            "highlight": _clean_highlight(raw.get("highlight")),
            "children": [],
        }
        if ntype == "group":
            opts = []
            for j, o in enumerate(raw.get("options") or []):
                if not isinstance(o, dict):
                    continue
                opts.append({
                    "id": str(o.get("id") or f"{nid}-o{j}"),
                    "text": str(o.get("text", o.get("label", ""))).strip(),
                    "confidence": coerce_conf(o.get("confidence")),
                    "evidence": [str(e) for e in (o.get("evidence") or []) if str(e).strip()],
                    "detail": (str(o["detail"]).strip() if o.get("detail") else None),
                    "highlight": _clean_highlight(o.get("highlight")),
                })
            n["options"] = opts
        # evidence/confidence sanity (non-fatal)
        if ntype in ("answer", "option", "note") and n["confidence"] is not None \
                and n["confidence"] >= 0.75 and not n["evidence"]:
            warn(f"node {nid}: green confidence ({n['confidence']}) but no evidence cited")
            warnings += 1
        by_id[nid] = n
        clean.append(n)

    # 2. wire parent -> children, find roots
    roots = []
    for n in clean:
        p = n["parent"]
        if p and p in by_id:
            by_id[p]["children"].append(n)
        else:
            if p:
                warn(f"node {n['id']}: parent '{p}' not found -> treated as a root")
                warnings += 1
            roots.append(n)
    for n in clean:
        n.pop("parent", None)

    # 3. single root (synthesized wrapper if the spec is a forest)
    title = spec.get("title") or arg_title or "Mind map"
    if len(roots) == 1:
        root = roots[0]
    else:
        root = {"id": "__root__", "type": "question", "text": title,
                "primary": False, "confidence": None, "evidence": [],
                "detail": None, "collapsed": False, "children": roots}

    proj = spec.get("project")
    if not proj and spec.get("project_root"):
        proj = os.path.basename(str(spec["project_root"]).rstrip("/"))

    out = {
        "meta": {
            "title": title,
            "mode": spec.get("mode") or arg_mode or "",
            "project": proj or "",
            "generated": spec.get("generated_at") or "",
        },
        "thresholds": {**DEFAULT_THRESHOLDS, **(spec.get("thresholds") or {})},
        "root": root,
    }
    if spec.get("palette"):
        out["palette"] = spec["palette"]
    return out, warnings


def read_asset(name):
    p = VENDOR / name
    if not p.exists():
        die(f"missing vendored asset: {p}\n  (re-run the skill's asset vendoring step)")
    return p.read_text(encoding="utf-8")


def b64_font(name):
    p = VENDOR / name
    if not p.exists():
        die(f"missing vendored font: {p}")
    return base64.b64encode(p.read_bytes()).decode("ascii")


def safe_js(s):
    # keep an inlined <script> from being terminated early by library/data content
    return s.replace("</script", "<\\/script")


def build_html(data):
    if not TEMPLATE.exists():
        die(f"missing template: {TEMPLATE}")
    html = TEMPLATE.read_text(encoding="utf-8")
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    repl = {
        "/*__ROUGH_JS__*/": safe_js(read_asset("rough.js")),
        "/*__D3_HIERARCHY_JS__*/": safe_js(read_asset("d3-hierarchy.min.js")),
        "/*__D3_FLEXTREE_JS__*/": safe_js(read_asset("d3-flextree.js")),
        "/*__MINDMAP_DATA__*/": data_json,
        "__FONT_400_B64__": b64_font("caveat-400.woff2"),
        "__FONT_700_B64__": b64_font("caveat-700.woff2"),
    }
    for token, value in repl.items():
        if token not in html:
            warn(f"template placeholder not found: {token}")
        html = html.replace(token, value)
    return html


def main():
    ap = argparse.ArgumentParser(description="Render a mind-map spec to a self-contained HTML file.")
    ap.add_argument("--spec", required=True, help="path to the flat JSON spec")
    ap.add_argument("--out", required=True, help="path to write the HTML file")
    ap.add_argument("--title", default=None, help="override the map title")
    ap.add_argument("--mode", default=None, help="mode tag shown in the toolbar")
    ap.add_argument("--open", action="store_true", help="open the result in a browser")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        die(f"spec not found: {spec_path}")
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"spec is not valid JSON: {e}")

    # A bundle ({maps:[...]}) holds several maps in one HTML; a single spec has {nodes:[...]}.
    if isinstance(spec.get("maps"), list) and spec["maps"]:
        warnings = 0
        maps = []
        for ms in spec["maps"]:
            md, w = normalize(ms, ms.get("title"), ms.get("mode"))
            maps.append(md)
            warnings += w
        data = {
            "bundle": True,
            "title": spec.get("title") or args.title or "Mind maps",
            "maps": maps,
        }
        n_nodes = sum(_count(m["root"]) for m in maps)
        label = f"bundle: {len(maps)} maps, {n_nodes} nodes"
    else:
        data, warnings = normalize(spec, args.title, args.mode)
        if args.title:
            data["meta"]["title"] = args.title
        if args.mode:
            data["meta"]["mode"] = args.mode
        n_nodes = _count(data["root"])
        label = f"mind map: {n_nodes} nodes"

    html = build_html(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    size_kb = out.stat().st_size / 1024
    print(f"  {label}, {size_kb:.0f} KB -> {out}")
    if warnings:
        print(f"  ({warnings} spec warning(s) above)", file=sys.stderr)

    if args.open:
        try:
            opened = webbrowser.open(out.resolve().as_uri())
            if not opened:
                print("  (could not auto-open a browser — open the file manually)")
        except Exception as e:  # headless / no display
            print(f"  (browser open skipped: {e})")
    print(out.resolve())


def _count(node):
    return 1 + sum(_count(c) for c in node.get("children", [])) + len(node.get("options", []))


if __name__ == "__main__":
    main()
