# atlas3d — the 3D viewer behind `sota-pool/atlas.html`

`viewer.js` is the source of the WebGL viewer that draws the SOTA
constellation in three dimensions (three.js + OrbitControls). It is bundled
into `../atlas3d.bundle.js`, a single minified IIFE that
`scripts/render_atlas.py` inlines verbatim, so the atlas opens with no network
and the renderer stays Python stdlib-only.

## Rebuild

```bash
npm install                 # pinned three and esbuild devDependencies
npm run build:atlas-viewer  # writes ../atlas3d.bundle.js and prints its sha256
```

Commit the rebuilt bundle together with the `viewer.js` change. The build
refuses output containing `</script` (it could not be inlined) and is
reproducible: same sources and pins, same bytes.

## Division of labour

The viewer never lays anything out. `render_atlas.py` computes every position,
orbital frame, edge and family tie deterministically and writes them into a
`<script type="application/json" id="atlas-data">` island; the viewer only
draws them. "Same atlas, same sky" therefore stays a property of the Python
renderer, and the starfield uses a fixed-seed generator, never `Math.random`.

## Scene contract (`version: 1`)

```text
{
  "version": 1,
  "atlas": <the atlas.json object, verbatim>,
  "positions": { "<system>.<planet>": [x, y, z], ... },
  "frames": { "<system>": { "center": [x, y, z], "u": [x, y, z], "v": [x, y, z] } },
  "edges": [ { "from": key, "to": key, "rel": str, "color": "#rrggbb", "inter": bool } ],
  "ties": [ { "family": str, "from": key, "to": key } ],
  "slot_colors": { "<slot>": "#rrggbb" },
  "orbit_radii": { "<orbit>": radius }
}
```

`u` and `v` are the orthonormal basis of a system's tilted orbital plane: a
planet on orbit `r` at angle `a` sits at `center + r·cos(a)·u + r·sin(a)·v`, and
its rings are drawn in that same plane.

## Page surface

`window.AtlasViewer.mount(container, scene, hooks)` returns a handle with
`setDim(keep | null)`, `zoom(factor)`, `reset()` and `focus(key)`.
`hooks.onSelect(key)` fires on a planet click and `hooks.onHover(key | null)`
on hover. The page's inline script owns the modal, the family chips and the
zoom buttons.
