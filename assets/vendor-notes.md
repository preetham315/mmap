# Vendored assets

Everything the renderer needs is inlined into a single offline HTML by
`scripts/render_mindmap.py` (it reads these files from `assets/vendor/` and
substitutes them into `assets/template.html`). Nothing is fetched at render time.

| File                         | Package                         | Version | License     | Source                                   |
| ---------------------------- | ------------------------------- | ------- | ----------- | ---------------------------------------- |
| `vendor/rough.js`            | roughjs (bundled UMD)           | 4.6.6   | MIT         | https://github.com/rough-stuff/rough     |
| `vendor/d3-hierarchy.min.js` | d3-hierarchy                    | 3.1.2   | ISC         | https://github.com/d3/d3-hierarchy       |
| `vendor/d3-flextree.js`      | d3-flextree (UMD)               | 2.1.2   | WTFPL       | https://github.com/Klortho/d3-flextree   |
| `vendor/caveat-400.woff2`    | @fontsource/caveat (Caveat 400) | 5.x     | SIL OFL 1.1 | https://fonts.google.com/specimen/Caveat |
| `vendor/caveat-700.woff2`    | @fontsource/caveat (Caveat 700) | 5.x     | SIL OFL 1.1 | https://fonts.google.com/specimen/Caveat |

All licenses permit embedding and redistribution. The font is re-declared as
`MMapHand` in the template's `@font-face` so the map is portable (the same
base64 is embedded into exported SVG/PNG).

## Re-vendoring

```sh
cd assets/vendor
curl -fsSL https://cdn.jsdelivr.net/npm/roughjs@4.6.6/bundled/rough.js -o rough.js
curl -fsSL https://cdn.jsdelivr.net/npm/d3-hierarchy@3.1.2/dist/d3-hierarchy.min.js -o d3-hierarchy.min.js
curl -fsSL https://cdn.jsdelivr.net/npm/d3-flextree@2.1.2/build/d3-flextree.js -o d3-flextree.js
curl -fsSL https://cdn.jsdelivr.net/npm/@fontsource/caveat@5.0.16/files/caveat-latin-400-normal.woff2 -o caveat-400.woff2
curl -fsSL https://cdn.jsdelivr.net/npm/@fontsource/caveat@5.0.16/files/caveat-latin-700-normal.woff2 -o caveat-700.woff2
```

## Notes

- **Load order matters:** `d3-hierarchy` then `d3-flextree`. Both attach to a
  shared `d3` global; flextree adds `d3.flextree` and bundles its own hierarchy
  internally, so the layout works even though we also load d3-hierarchy.
- **Font swap:** to match Excalidraw more exactly you can drop in **Excalifont**
  (OFL, https://github.com/excalidraw/excalidraw) as `caveat-400.woff2` /
  `caveat-700.woff2` (keep the filenames, or update them in `render_mindmap.py`).
  Caveat is the default for license certainty and single-file simplicity.
