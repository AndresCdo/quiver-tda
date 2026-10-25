"""Deterministic renderer: a green atlas to one self-contained HTML file.

Reads ``sota-pool/atlas.json`` and writes a single ``atlas.html``: every
system placed in ONE shared 3D sky (family neighborhoods on a golden spiral,
each lifted to its own height; systems sorted by id, each on its own tilted
orbital plane — the same atlas always draws the same sky), intra-system links
as straight segments, inter-system links as arcs running planet to planet
across systems, and dashed ties between planets sharing a family name.

The scene is computed here and written as a JSON data island; the vendored
three.js viewer (``assets/atlas3d.bundle.js``, rebuilt with
``npm run build:atlas-viewer``) is inlined verbatim and only draws it — no CDN,
no network at view time. Clicking a planet shows its detail and abstract
quote; a family filter dims what does not belong; hovering a planet
highlights its cross-system links; drag orbits, wheel zooms.

Exit 0 on a written file, 1 when the atlas fails this module's own shape
read (run the checker first — it names violations, this one only refuses
to draw), 2 on usage, unreadable input, or a missing/unsafe viewer bundle.

Stdlib only.
"""

from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

SLOT_COLORS = {
    "sun": "#e8b339",
    "branch": "#7fb069",
    "topic_app": "#5aa9e6",
    "topic_ai": "#7f6ae6",
    "problem": "#e65a5a",
    "application": "#5ad1e6",
    "family": "#9b7ede",
    "novelty": "#e67e22",
    "contribution": "#e879f9",
    "result": "#2ecc71",
    "conclusion": "#95a5a6",
}

REL_COLORS = {
    "about": "#4a5a80",
    "addresses": "#8a93ad",
    "extends": "#2ecc71",
    "contradicts": "#e65a5a",
    "supports": "#5aa9e6",
    "yields": "#e8b339",
    "shares-family-with": "#9b7ede",
}

ORBIT_RADII = {0: 0, 1: 90, 2: 170, 3: 250}
CLUSTER_STEP = 3400
MEMBER_STEP = 660
GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))
PHI = (math.sqrt(5) - 1) / 2
FAMILY_LIFT = 900
MEMBER_LIFT = 260
TILT_MAX = 0.9
VIEWER = Path(__file__).resolve().parent.parent / "assets" / "atlas3d.bundle.js"


def _spread(index: int) -> float:
    """A deterministic value in [-1, 1): the golden-ratio sequence, so
    consecutive indices land far apart without any randomness."""
    return 2 * ((index * PHI) % 1.0) - 1


def _family_of(system: dict) -> str:
    """The group this system belongs to: its one family planet's label.
    Systems with none gather under the empty name — the checker refuses
    them, but the renderer still draws something rather than crashing."""
    for planet in system.get("planets") or []:
        if isinstance(planet, dict) and planet.get("slot") == "family":
            label = planet.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()
    return ""


def _system_centers(systems: list[dict]) -> dict[str, tuple[float, float, float]]:
    """One shared sky, grouped by family: each family owns a cluster center
    on an outer golden spiral lifted to its own height, and its member
    systems spiral locally around it. A family reads as a neighborhood.
    Pure function of sorted ids and labels — deterministic by construction."""
    by_family: dict[str, list[str]] = {}
    for system in sorted(systems, key=lambda s: s["id"]):
        by_family.setdefault(_family_of(system), []).append(system["id"])
    centers: dict[str, tuple[float, float, float]] = {}
    for findex, fam in enumerate(sorted(by_family)):
        radius = CLUSTER_STEP * math.sqrt(findex)
        angle = findex * GOLDEN_ANGLE
        ccx, ccy = radius * math.cos(angle), radius * math.sin(angle)
        ccz = FAMILY_LIFT * _spread(findex)
        for mindex, sid in enumerate(by_family[fam]):
            mradius = MEMBER_STEP * math.sqrt(mindex)
            mangle = mindex * GOLDEN_ANGLE
            centers[sid] = (
                round(ccx + mradius * math.cos(mangle), 1),
                round(ccy + mradius * math.sin(mangle), 1),
                round(ccz + MEMBER_LIFT * _spread(mindex + 1), 1),
            )
    return centers


def _orbital_frame(index: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The orthonormal basis (u, v) of one system's orbital plane: spun about
    the vertical by the golden angle, then tilted out of the horizontal, so
    neighboring systems never share a plane. Deterministic by index."""
    spin = index * GOLDEN_ANGLE
    tilt = TILT_MAX * _spread(index + 1)
    u = (math.cos(spin), math.sin(spin), 0.0)
    v = (-math.sin(spin) * math.cos(tilt), math.cos(spin) * math.cos(tilt), math.sin(tilt))
    return tuple(round(c, 4) for c in u), tuple(round(c, 4) for c in v)


def _local_positions(planets: list[dict]) -> dict[str, tuple[float, float]]:
    """System-local layout: orbit radius by slot, evenly spaced angles in id
    order — the same planets always draw the same system."""
    by_orbit: dict[int, list[dict]] = {}
    for planet in planets:
        by_orbit.setdefault(planet["orbit"], []).append(planet)
    positions: dict[str, tuple[float, float]] = {}
    for orbit in sorted(by_orbit):
        members = sorted(by_orbit[orbit], key=lambda p: p["id"])
        radius = ORBIT_RADII.get(orbit, 250)
        if radius == 0:
            positions[members[0]["id"]] = (0.0, 0.0)
            continue
        for index, planet in enumerate(members):
            angle = 2 * math.pi * index / len(members) - math.pi / 2
            positions[planet["id"]] = (
                round(radius * math.cos(angle), 1),
                round(radius * math.sin(angle), 1),
            )
    return positions


def _family_ties(atlas: dict, positions: dict[str, list[float]]) -> list[dict]:
    """One tie per consecutive pair of planets sharing a family name,
    chaining them across systems in system-id order. This draws identity,
    not findings: families are the only planets two systems may share by
    name, so equal labels ARE the same family and the tie only makes that
    visible. Deterministic — same atlas, same ties."""
    by_label: dict[str, list[tuple[str, str]]] = {}
    for system in atlas["systems"]:
        for planet in system["planets"]:
            if planet.get("slot") == "family":
                by_label.setdefault(str(planet.get("label")), []).append(
                    (system["id"], planet["id"]))
    ties = []
    for label in sorted(by_label):
        members = [f"{sid}.{pid}" for sid, pid in sorted(by_label[label])]
        for first, second in zip(members, members[1:]):
            if first in positions and second in positions:
                ties.append({"family": label, "from": first, "to": second})
    return ties


def _scene(atlas: dict) -> dict:
    """Everything the viewer draws, precomputed: the viewer lays out nothing,
    so the same atlas always yields the same scene."""
    centers = _system_centers(atlas["systems"])
    positions: dict[str, list[float]] = {}
    frames: dict[str, dict] = {}
    for index, system in enumerate(sorted(atlas["systems"], key=lambda s: s["id"])):
        center = centers[system["id"]]
        u, v = _orbital_frame(index)
        frames[system["id"]] = {"center": list(center), "u": list(u), "v": list(v)}
        for pid, (lx, ly) in _local_positions(system["planets"]).items():
            positions[f"{system['id']}.{pid}"] = [
                round(center[axis] + lx * u[axis] + ly * v[axis], 1) for axis in range(3)]
    edges = []
    for link in sorted(atlas["links"],
                       key=lambda l: (str(l.get("from_system")), str(l.get("from")),
                                      str(l.get("to_system")), str(l.get("to")))):
        source = f"{link.get('from_system')}.{link.get('from')}"
        target = f"{link.get('to_system')}.{link.get('to')}"
        if source not in positions or target not in positions:
            continue
        edges.append({"from": source, "to": target, "rel": link.get("rel"),
                      "color": REL_COLORS.get(link.get("rel"), "#4a5a80"),
                      "inter": link.get("from_system") != link.get("to_system")})
    return {
        "version": 1,
        "atlas": atlas,
        "positions": dict(sorted(positions.items())),
        "frames": dict(sorted(frames.items())),
        "edges": edges,
        "ties": _family_ties(atlas, positions),
        "slot_colors": SLOT_COLORS,
        "orbit_radii": {str(orbit): radius for orbit, radius in ORBIT_RADII.items() if radius},
    }


def _readable_shape(atlas: object) -> str | None:
    if not isinstance(atlas, dict):
        return "ATLAS_NOT_AN_OBJECT"
    if not isinstance(atlas.get("systems"), list) or not atlas["systems"]:
        return "SYSTEMS_NOT_A_NONEMPTY_LIST"
    if not isinstance(atlas.get("links"), list):
        return "LINKS_NOT_A_LIST"
    for system in atlas["systems"]:
        if not isinstance(system, dict) or not isinstance(system.get("planets"), list):
            return "SYSTEM_MALFORMED"
    return None


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<style>
html,body{height:100%}
body{font-family:system-ui,sans-serif;background:#0a0a10;color:#e4e4ed;margin:0;padding:12px 16px;box-sizing:border-box;display:flex;flex-direction:column}
h1{font-size:18px;font-weight:600;margin:0 0 8px;letter-spacing:.02em}
.sky{flex:1 1 auto;min-height:420px;width:100%;background:#0a0a10;border:1px solid #1e2236;border-radius:10px;overflow:hidden;cursor:grab}
.sky:active{cursor:grabbing}
#panel{color:#9aa3bd;font-size:13px;margin:0 0 8px}
#overlay{position:fixed;inset:0;background:rgba(5,5,10,.65);display:none;align-items:center;justify-content:center;z-index:10}
#overlay.open{display:flex}
#modal{background:#11131f;border:1px solid #9b7ede;border-radius:10px;padding:16px 20px;max-width:580px;max-height:82vh;overflow:auto;box-shadow:0 0 40px rgba(155,126,222,.25)}
#modal h3{margin:0 0 6px}
#modal .quote{font-style:italic;color:#b9c4de;border-left:3px solid #9b7ede;margin:10px 0;padding-left:10px}
#modalclose{float:right;cursor:pointer;font-size:14px;padding:2px 10px;background:#1a1d2e;color:#e4e4ed;border:1px solid #2a3350;border-radius:6px}
#famlegend,#rellegend,#toolbar{margin:0 0 6px;font-size:13px;color:#9aa3bd}
.famchip{margin:2px;padding:3px 12px;cursor:pointer;border-radius:12px;border:1px solid #9b7ede;background:#14172a;color:#e4e4ed;font-size:12px}
.famchip.on{background:#9b7ede;color:#0a0a10}
.dot{display:inline-block;width:16px;height:0;border-top:2px solid;margin:0 4px 3px 10px;vertical-align:middle}
#toolbar button{font-size:13px;margin-right:6px;padding:3px 12px;cursor:pointer;background:#14172a;color:#e4e4ed;border:1px solid #2a3350;border-radius:6px}
</style>
</head>
<body>
<h1>@@HEADING@@</h1>
<div id="panel">Drag to orbit, right-drag to pan, wheel to zoom. Hover a planet to trace its cross-system links; click to read it; double-click to fly to it.</div>
<div id="overlay"><div id="modal"><button id="modalclose">close</button><div id="modalbody"></div></div></div>
<div id="famlegend"><em>Families:</em> <span id="famchips"></span></div>
<div id="rellegend"><em>Links:</em> <span class="dot" style="border-color:#2ecc71"></span>extends <span class="dot" style="border-color:#5aa9e6"></span>supports <span class="dot" style="border-color:#e65a5a"></span>contradicts <span class="dot" style="border-color:#8a93ad"></span>addresses <span class="dot" style="border-color:#9b7ede;border-top-style:dashed"></span>shared family <span class="dot" style="border-color:#e8b339"></span>yields <span class="dot" style="border-color:#4a5a80"></span>about</div>
<div id="toolbar"><button id="zoomin">zoom +</button><button id="zoomout">zoom −</button><button id="zoomreset">reset view</button></div>
<div id="sky" class="sky"></div>
<script type="application/json" id="atlas-data">@@DATA@@</script>
<script>
@@VIEWER@@
</script>
<script>
const SCENE = JSON.parse(document.getElementById('atlas-data').textContent);
const ATLAS = SCENE.atlas;
const PLANETS = new Map();
ATLAS.systems.forEach(s => s.planets.forEach(p => PLANETS.set(s.id + '.' + p.id, {system: s, planet: p})));
const panel = document.getElementById('modalbody');
const overlay = document.getElementById('overlay');
function closeModal() { overlay.classList.remove('open'); }
document.getElementById('modalclose').addEventListener('click', closeModal);
overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
function line(tag, text, cls) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (cls) el.className = cls;
  return el;
}
function openModal(nodes) {
  panel.replaceChildren(...nodes);
  overlay.classList.add('open');
}
function showPlanet(key) {
  const entry = PLANETS.get(key);
  if (!entry) return;
  const p = entry.planet;
  const ev = p.evidence || {};
  openModal([
    line('h3', p.label),
    line('p', p.slot + ' · orbit ' + p.orbit + ' · ' + (p.provenance || '') + ' · ' + (entry.system.title || entry.system.id)),
    line('p', p.detail || ''),
    line('p', ev.quote || '', 'quote'),
    line('small', (ev.origin || '') + ' · retrieved ' + (ev.retrieved || '')),
  ]);
}
let activeFam = null;
function familyKeep() {
  if (activeFam === null) return null;
  const keep = new Set();
  ATLAS.systems.forEach(s => {
    if (s.planets.some(p => p.slot === 'family' && p.label === activeFam))
      s.planets.forEach(p => keep.add(s.id + '.' + p.id));
  });
  return keep;
}
function hoverKeep(key) {
  const keep = new Set([key]);
  SCENE.edges.forEach(e => {
    if (e.inter && (e.from === key || e.to === key)) { keep.add(e.from); keep.add(e.to); }
  });
  const entry = PLANETS.get(key);
  if (entry && entry.planet.slot === 'family') {
    PLANETS.forEach((other, otherKey) => {
      if (other.planet.slot === 'family' && other.planet.label === entry.planet.label) keep.add(otherKey);
    });
  }
  return keep;
}
const viewer = AtlasViewer.mount(document.getElementById('sky'), SCENE, {
  onSelect: showPlanet,
  onHover: key => { if (viewer) viewer.setDim(key ? hoverKeep(key) : familyKeep()); },
});
document.getElementById('zoomin').addEventListener('click', () => viewer && viewer.zoom(1.5));
document.getElementById('zoomout').addEventListener('click', () => viewer && viewer.zoom(1 / 1.5));
document.getElementById('zoomreset').addEventListener('click', () => {
  if (!viewer) return;
  activeFam = null;
  document.querySelectorAll('.famchip').forEach(c => c.classList.remove('on'));
  viewer.reset();
});
const chips = document.getElementById('famchips');
const fams = {};
ATLAS.systems.forEach(s => s.planets.forEach(p => {
  if (p.slot === 'family') fams[p.label] = (fams[p.label] || 0) + 1;
}));
Object.keys(fams).sort().forEach(label => {
  const b = document.createElement('button');
  b.textContent = label + ' (' + fams[label] + ')';
  b.className = 'famchip';
  b.addEventListener('click', () => {
    activeFam = (activeFam === label) ? null : label;
    document.querySelectorAll('.famchip').forEach(c => c.classList.toggle('on', c === b && activeFam === label));
    if (viewer) viewer.setDim(familyKeep());
  });
  chips.appendChild(b);
});
</script>
</body>
</html>
"""


def _viewer_bundle() -> str:
    return VIEWER.read_text(encoding="utf-8")


def render(atlas: dict, viewer: str | None = None, *,
           title: str | None = None, heading: str | None = None) -> str:
    """The whole page. ``title`` and ``heading`` default to the SOTA
    constellation's own words, so a caller that says nothing gets the byte it
    always got; a caller rendering another domain's sky — a proposal overlaid
    on this one — names it instead of borrowing a title that would be false.
    """
    bundle = _viewer_bundle() if viewer is None else viewer
    if "</script" in bundle.lower():
        raise ValueError("the viewer bundle contains </script and cannot be inlined")
    if title is None:
        title, heading = "SOTA constellation", "SOTA constellation — one sky"
    elif heading is None:
        # One name is enough: a caller who names the page means both places it
        # is read, and a heading left behind would contradict the tab title.
        heading = title
    named = PAGE.replace("@@TITLE@@", html.escape(title))
    named = named.replace("@@HEADING@@", html.escape(heading))
    data = json.dumps(_scene(atlas)).replace("<", "\\u003c")
    head, rest = named.split("@@DATA@@")
    middle, tail = rest.split("@@VIEWER@@")
    return head + data + middle + bundle + tail


def main(argv: list[str]) -> int:
    inputs: list[str] = []
    out_path: Path | None = None
    title: str | None = None
    tokens = argv[1:]
    index = 0
    while index < len(tokens):
        if tokens[index] == "--out" and index + 1 < len(tokens):
            out_path = Path(tokens[index + 1])
            index += 2
        elif tokens[index] == "--title" and index + 1 < len(tokens):
            title = tokens[index + 1]
            index += 2
        else:
            inputs.append(tokens[index])
            index += 1
    if len(inputs) != 1 or out_path is None:
        print("usage: render_atlas.py sota-pool/atlas.json --out sota-pool/atlas.html "
              "[--title <text>]",
              file=sys.stderr)
        return 2
    try:
        raw = Path(inputs[0]).read_text(encoding="utf-8")
    except OSError as error:
        print(f"ATLAS_UNREADABLE: {error}", file=sys.stderr)
        return 2
    try:
        atlas = json.loads(raw)
    except json.JSONDecodeError as error:
        print(f"ATLAS_NOT_JSON: {error}", file=sys.stderr)
        return 2
    shape_error = _readable_shape(atlas)
    if shape_error is not None:
        print(f"{shape_error}: run the checker first", file=sys.stderr)
        return 1
    try:
        page = render(atlas, title=title)
    except OSError as error:
        print(f"ATLAS_VIEWER_MISSING: {error} (run npm run build:atlas-viewer)",
              file=sys.stderr)
        return 2
    except ValueError as error:
        print(f"ATLAS_VIEWER_UNSAFE: {error}", file=sys.stderr)
        return 2
    out_path.write_text(page, encoding="utf-8")
    systems = len(atlas["systems"])
    print(f"ATLAS_RENDERED: {systems} systems in one sky -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
