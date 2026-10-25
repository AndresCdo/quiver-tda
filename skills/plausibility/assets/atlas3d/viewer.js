// Atlas 3D viewer: draws the scene render_atlas.py precomputes.
//
// Built into ../atlas3d.bundle.js by scripts/build-atlas-viewer.mjs and
// inlined verbatim into every sota-pool/atlas.html, so the page opens with no
// network. The viewer never lays anything out: every position, orbital frame,
// edge and family tie arrives precomputed in the scene (see README.md), which
// keeps "same atlas, same sky" a property of the Python renderer alone.
//
// Public surface: window.AtlasViewer.mount(container, scene, hooks) -> handle
//   hooks.onSelect(key)        click on a planet ("<system>.<planet>")
//   hooks.onHover(key | null)  pointer enters / leaves a planet
//   handle.setDim(keep | null) dim every planet not in the Set `keep`
//   handle.zoom(factor)        dolly toward the orbit target (>1 = closer)
//   handle.reset()             restore the framed home view
//   handle.focus(key)          fly the orbit target to one planet

import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  FogExp2,
  InstancedMesh,
  LineBasicMaterial,
  LineDashedMaterial,
  LineLoop,
  LineSegments,
  MeshBasicMaterial,
  Object3D,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  Scene,
  SphereGeometry,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
} from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const BACKGROUND = 0x0a0a10;
const DIM = 0.16;
const PICK_RADIUS_PX = 14;
const SUN_RADIUS = 22;
const PLANET_RADIUS = 10;
// Halos and labels keep a fixed on-screen size, so a 25-system sky reads as a
// field of glowing points from afar and resolves into spheres up close.
const SUN_HALO_PX = 30;
const PLANET_HALO_PX = 15;
const LABEL_SCREEN_HEIGHT = 0.026;
const CURVE_STEPS = 18;

function glowTexture() {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.2, 'rgba(255,255,255,0.55)');
  g.addColorStop(0.5, 'rgba(255,255,255,0.12)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  return texture;
}

function labelSprite(text, screenHeight) {
  const font = 44;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  ctx.font = `600 ${font}px system-ui, sans-serif`;
  const width = Math.ceil(ctx.measureText(text).width) + 24;
  canvas.width = width;
  canvas.height = font + 20;
  ctx.font = `600 ${font}px system-ui, sans-serif`;
  ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(0,0,0,0.9)';
  ctx.shadowBlur = 8;
  ctx.fillStyle = '#e4e4ed';
  ctx.fillText(text, 12, canvas.height / 2);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  const sprite = new Sprite(new SpriteMaterial({
    map: texture, transparent: true, depthWrite: false, depthTest: false, sizeAttenuation: false, opacity: 0.85,
  }));
  sprite.scale.set(screenHeight * (canvas.width / canvas.height), screenHeight, 1);
  sprite.center.set(0.5, -0.6);
  return sprite;
}

// A deterministic starfield: an LCG, never Math.random, so two openings of the
// same file show the same sky.
function starfield(center, radius) {
  let seed = 1234567;
  const next = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  const count = 1600;
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const theta = next() * Math.PI * 2;
    const phi = Math.acos(2 * next() - 1);
    const r = radius * (3 + next() * 3);
    positions[i * 3] = center.x + r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = center.y + r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = center.z + r * Math.cos(phi);
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new BufferAttribute(positions, 3));
  return new Points(geometry, new PointsMaterial({
    color: 0x6b7090, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0.7, depthWrite: false,
  }));
}

function curvePoints(a, b, lift) {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  mid.z += lift;
  const out = [];
  for (let i = 0; i <= CURVE_STEPS; i++) {
    const t = i / CURVE_STEPS;
    const s = 1 - t;
    out.push(new Vector3(
      s * s * a.x + 2 * s * t * mid.x + t * t * b.x,
      s * s * a.y + 2 * s * t * mid.y + t * t * b.y,
      s * s * a.z + 2 * s * t * mid.z + t * t * b.z,
    ));
  }
  return out;
}

function mount(container, data, hooks = {}) {
  let renderer;
  try {
    renderer = new WebGLRenderer({ antialias: true });
  } catch (error) {
    container.textContent = 'This atlas needs WebGL, which this browser could not start.';
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(BACKGROUND, 1);
  container.style.position = container.style.position || 'relative';
  container.appendChild(renderer.domElement);
  renderer.domElement.style.display = 'block';

  const tooltip = document.createElement('div');
  tooltip.className = 'atlas-tip';
  tooltip.style.cssText = 'position:absolute;pointer-events:none;display:none;padding:3px 8px;'
    + 'border-radius:6px;background:rgba(10,10,16,.88);border:1px solid #2a3350;color:#e4e4ed;'
    + 'font:12px system-ui,sans-serif;white-space:nowrap;transform:translate(-50%,-130%)';
  container.appendChild(tooltip);

  const scene = new Scene();
  const planets = new Map();
  for (const system of data.atlas.systems) {
    for (const planet of system.planets) planets.set(`${system.id}.${planet.id}`, { system, planet });
  }
  const keys = Object.keys(data.positions).sort();
  const index = new Map(keys.map((key, i) => [key, i]));
  const points = keys.map((key) => new Vector3(...data.positions[key]));

  // Frame: the bounding sphere around the bounding-box center of every planet.
  const low = new Vector3(Infinity, Infinity, Infinity);
  const high = new Vector3(-Infinity, -Infinity, -Infinity);
  points.forEach((p) => { low.min(p); high.max(p); });
  const center = points.length ? low.clone().add(high).multiplyScalar(0.5) : new Vector3();
  const radius = Math.max(400, ...points.map((p) => p.distanceTo(center)));
  scene.fog = new FogExp2(BACKGROUND, 0.35 / radius);
  scene.add(starfield(center, radius));

  // Planets: one instanced sphere mesh plus an additive glow halo.
  const baseColors = keys.map((key) => {
    const slot = planets.get(key)?.planet.slot;
    return new Color(data.slot_colors[slot] || '#cccccc');
  });
  const isSun = keys.map((key) => planets.get(key)?.planet.slot === 'sun');
  const mesh = new InstancedMesh(new SphereGeometry(1, 20, 14), new MeshBasicMaterial(), keys.length);
  const dummy = new Object3D();
  keys.forEach((key, i) => {
    dummy.position.copy(points[i]);
    dummy.scale.setScalar(isSun[i] ? SUN_RADIUS : PLANET_RADIUS);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
    mesh.setColorAt(i, baseColors[i]);
  });
  scene.add(mesh);

  const glow = glowTexture();
  function halo(filter, size) {
    const chosen = keys.map((_, i) => i).filter(filter);
    const position = new Float32Array(chosen.length * 3);
    const color = new Float32Array(chosen.length * 3);
    chosen.forEach((i, j) => {
      position.set(points[i].toArray(), j * 3);
      color.set(baseColors[i].toArray(), j * 3);
    });
    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new BufferAttribute(position, 3));
    geometry.setAttribute('color', new BufferAttribute(color, 3));
    const cloud = new Points(geometry, new PointsMaterial({
      size: size * renderer.getPixelRatio(), map: glow, vertexColors: true, transparent: true,
      depthWrite: false, blending: AdditiveBlending, sizeAttenuation: false,
    }));
    scene.add(cloud);
    return { cloud, chosen };
  }
  const halos = [halo((i) => isSun[i], SUN_HALO_PX), halo((i) => !isSun[i], PLANET_HALO_PX)];

  // Orbit rings in each system's own tilted plane.
  const ringMaterial = new LineBasicMaterial({ color: 0x2a3350, transparent: true, opacity: 0.55 });
  for (const [sid, frame] of Object.entries(data.frames)) {
    const system = data.atlas.systems.find((s) => s.id === sid);
    const orbits = [...new Set(system.planets.map((p) => p.orbit))].filter((o) => o > 0).sort();
    const c = new Vector3(...frame.center);
    const u = new Vector3(...frame.u);
    const v = new Vector3(...frame.v);
    for (const orbit of orbits) {
      const r = data.orbit_radii[String(orbit)] || 250;
      const ring = [];
      for (let k = 0; k < 96; k++) {
        const a = (k / 96) * Math.PI * 2;
        ring.push(c.clone().addScaledVector(u, r * Math.cos(a)).addScaledVector(v, r * Math.sin(a)));
      }
      scene.add(new LineLoop(new BufferGeometry().setFromPoints(ring), ringMaterial));
    }
    const label = labelSprite(String(system.title || sid).slice(0, 64), LABEL_SCREEN_HEIGHT);
    label.position.copy(c);
    scene.add(label);
  }

  // Edges: intra-system straight, inter-system arcs lifted out of the plane.
  const edgeVerts = [];
  const edgeColors = [];
  const edgeSpans = [];
  for (const edge of data.edges) {
    const i = index.get(edge.from);
    const j = index.get(edge.to);
    if (i === undefined || j === undefined) continue;
    const path = edge.inter
      ? curvePoints(points[i], points[j], points[i].distanceTo(points[j]) * 0.25)
      : [points[i], points[j]];
    const color = new Color(edge.color);
    const start = edgeColors.length / 3;
    for (let k = 0; k < path.length - 1; k++) {
      edgeVerts.push(...path[k].toArray(), ...path[k + 1].toArray());
      edgeColors.push(...color.toArray(), ...color.toArray());
    }
    edgeSpans.push({ from: edge.from, to: edge.to, start, end: edgeColors.length / 3, color, inter: edge.inter });
  }
  const edgeGeometry = new BufferGeometry();
  edgeGeometry.setAttribute('position', new BufferAttribute(new Float32Array(edgeVerts), 3));
  edgeGeometry.setAttribute('color', new BufferAttribute(new Float32Array(edgeColors), 3));
  scene.add(new LineSegments(edgeGeometry, new LineBasicMaterial({
    vertexColors: true, transparent: true, opacity: 0.9, blending: AdditiveBlending, depthWrite: false,
  })));

  // Family ties: dashed arcs chaining planets that share a family name.
  for (const tie of data.ties) {
    const i = index.get(tie.from);
    const j = index.get(tie.to);
    if (i === undefined || j === undefined) continue;
    const path = curvePoints(points[i], points[j], points[i].distanceTo(points[j]) * 0.35);
    const segments = [];
    for (let k = 0; k < path.length - 1; k++) segments.push(path[k], path[k + 1]);
    const line = new LineSegments(new BufferGeometry().setFromPoints(segments), new LineDashedMaterial({
      color: 0x9b7ede, dashSize: 40, gapSize: 28, transparent: true, opacity: 0.6, depthWrite: false,
    }));
    line.computeLineDistances();
    scene.add(line);
  }

  const FOV = 50;
  const camera = new PerspectiveCamera(FOV, 1, radius / 500, radius * 40);
  camera.up.set(0, 0, 1);
  // The sky is flatter than its bounding sphere, so frame a little inside
  // the sphere-fit distance; the full sphere would leave most of the view empty.
  const distance = (radius / Math.sin((FOV / 2) * Math.PI / 180)) * 0.8;
  const home = {
    position: center.clone().add(new Vector3(0, -0.85, 0.53).setLength(distance)),
    target: center.clone(),
  };
  camera.position.copy(home.position);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.copy(home.target);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.35;
  controls.addEventListener('start', () => { controls.autoRotate = false; });

  function resize() {
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;
    renderer.setSize(width, height, false);
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(container);
  resize();

  // Dimming recolors instances, halos and edge vertices in place.
  function paint(keep) {
    const lit = (key) => !keep || keep.has(key);
    keys.forEach((key, i) => {
      mesh.setColorAt(i, lit(key) ? baseColors[i] : baseColors[i].clone().multiplyScalar(DIM));
    });
    mesh.instanceColor.needsUpdate = true;
    for (const { cloud, chosen } of halos) {
      const attr = cloud.geometry.getAttribute('color');
      chosen.forEach((i, j) => {
        const c = lit(keys[i]) ? baseColors[i] : baseColors[i].clone().multiplyScalar(DIM * 0.5);
        attr.setXYZ(j, c.r, c.g, c.b);
      });
      attr.needsUpdate = true;
    }
    const colors = edgeGeometry.getAttribute('color');
    for (const span of edgeSpans) {
      const on = !keep || (keep.has(span.from) && keep.has(span.to));
      const c = on ? span.color : span.color.clone().multiplyScalar(DIM * 0.6);
      for (let k = span.start; k < span.end; k++) colors.setXYZ(k, c.r, c.g, c.b);
    }
    colors.needsUpdate = true;
  }

  // Screen-space picking: the nearest planet within a few pixels.
  const projected = new Vector3();
  function pick(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let best = null;
    let bestDistance = PICK_RADIUS_PX;
    points.forEach((p, i) => {
      projected.copy(p).project(camera);
      if (projected.z > 1) return;
      const sx = (projected.x + 1) / 2 * rect.width;
      const sy = (1 - projected.y) / 2 * rect.height;
      const d = Math.hypot(sx - x, sy - y);
      if (d < bestDistance) { bestDistance = d; best = { key: keys[i], sx, sy }; }
    });
    return best;
  }

  let hovered = null;
  let down = null;
  renderer.domElement.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY }; });
  renderer.domElement.addEventListener('pointermove', (e) => {
    const hit = pick(e);
    const key = hit ? hit.key : null;
    renderer.domElement.style.cursor = key ? 'pointer' : 'grab';
    if (hit) {
      const entry = planets.get(key);
      tooltip.textContent = `${entry.planet.label} [${entry.planet.slot}]`;
      tooltip.style.left = `${hit.sx}px`;
      tooltip.style.top = `${hit.sy}px`;
      tooltip.style.display = 'block';
    } else {
      tooltip.style.display = 'none';
    }
    if (key !== hovered) {
      hovered = key;
      if (hooks.onHover) hooks.onHover(key);
    }
  });
  renderer.domElement.addEventListener('pointerleave', () => {
    tooltip.style.display = 'none';
    if (hovered !== null) { hovered = null; if (hooks.onHover) hooks.onHover(null); }
  });
  renderer.domElement.addEventListener('click', (e) => {
    if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
    const hit = pick(e);
    if (hit && hooks.onSelect) hooks.onSelect(hit.key);
  });

  let flight = null;
  function focus(key) {
    const i = index.get(key);
    if (i === undefined) return;
    controls.autoRotate = false;
    const offset = camera.position.clone().sub(controls.target).setLength(radius * 0.45);
    flight = { target: points[i].clone(), position: points[i].clone().add(offset), t: 0 };
  }
  renderer.domElement.addEventListener('dblclick', (e) => {
    const hit = pick(e);
    if (hit) focus(hit.key);
  });

  function animate() {
    if (flight) {
      flight.t = Math.min(1, flight.t + 0.06);
      controls.target.lerp(flight.target, flight.t);
      camera.position.lerp(flight.position, flight.t);
      if (flight.t >= 1) flight = null;
    }
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  animate();

  return {
    setDim: paint,
    focus,
    zoom(factor) {
      controls.autoRotate = false;
      const offset = camera.position.clone().sub(controls.target).multiplyScalar(1 / factor);
      camera.position.copy(controls.target).add(offset);
    },
    reset() {
      flight = null;
      controls.target.copy(home.target);
      camera.position.copy(home.position);
      paint(null);
    },
  };
}

window.AtlasViewer = { mount };
