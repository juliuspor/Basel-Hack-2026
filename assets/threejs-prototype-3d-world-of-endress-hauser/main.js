// Find my Bike Slot: a low-poly, street-level model of Christoph-Merian-Ring
// between the two bicycle stations, built directly in three.js from the
// OpenStreetMap extract, Kenney CC0 models, and Street View observations.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// Archived in assets/: the OSM extract stays shared in campus-map/, the roof
// colours and Kenney models travel with this folder.
const ASSETS = '../';
const LON0 = 7.59825, LAT0 = 47.48785;
const SX = 111320 * Math.cos(LAT0 * Math.PI / 180), SY = 111132;
// Local metres: x east, y north. three.js: X = x, Y = up, Z = -y.
const V3 = (x, y, h = 0) => new THREE.Vector3(x, h, -y);
const BOX = { x0: 40, x1: 285, y0: -195, y1: 105 };   // the corridor and one block either side
const inBox = (p) => p.x > BOX.x0 && p.x < BOX.x1 && p.y > BOX.y0 && p.y < BOX.y1;

function rng(seed) {   // mulberry32: repeatable "random" placement
  return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
const srgb = (r, g, b) => new THREE.Color().setRGB(r / 255, g / 255, b / 255, THREE.SRGBColorSpace);
const std = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.85, flatShading: true, ...o });

// ---------------------------------------------------------------- renderer
const app = document.getElementById('app');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
app.appendChild(renderer.domElement);
const labels = new CSS2DRenderer();
labels.setSize(innerWidth, innerHeight);
Object.assign(labels.domElement.style, { position: 'fixed', inset: '0', pointerEvents: 'none' });
document.body.appendChild(labels.domElement);

const scene = new THREE.Scene();
const HORIZON = srgb(214, 228, 240);
scene.fog = new THREE.Fog(HORIZON, 140, 520);
const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.1, 2000);

// Sky dome: soft vertical gradient, light blue as in the Street View frames.
scene.add(new THREE.Mesh(new THREE.SphereGeometry(900, 32, 16), new THREE.ShaderMaterial({
  side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { top: { value: srgb(96, 152, 222) }, horizon: { value: HORIZON } },
  vertexShader: 'varying vec3 p; void main(){ p = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }',
  fragmentShader: 'uniform vec3 top; uniform vec3 horizon; varying vec3 p; void main(){ gl_FragColor = vec4(mix(horizon, top, pow(max(p.y,0.), 0.55)), 1.); }',
})));

scene.add(new THREE.HemisphereLight(srgb(205, 225, 255), srgb(150, 140, 120), 1.25));
const sun = new THREE.DirectionalLight(srgb(255, 244, 226), 2.6);
const CENTER = V3(140, -35);
sun.position.copy(CENTER).add(new THREE.Vector3(-110, 165, 125));   // afternoon sun from the south-west
sun.target.position.copy(CENTER);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -170, right: 170, top: 170, bottom: -170, near: 10, far: 500 });
sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.04;
scene.add(sun, sun.target);

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const ao = new GTAOPass(scene, camera, innerWidth, innerHeight);
ao.updateGtaoMaterial({ radius: 0.9, distanceExponent: 1.6, thickness: 1.0, scale: 1.0 });
ao.blendIntensity = 0.6;
composer.addPass(ao);
composer.addPass(new OutputPass());

// ---------------------------------------------------------------- geometry helpers
function ribbon(pts, width, h, mat, offset = 0) {
  // A flat strip along a polyline; positive offset lies left of travel.
  const pos = [], idx = [], uvs = [];
  pts.forEach((p, i) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    let tx = b.x - a.x, ty = b.y - a.y; const l = Math.hypot(tx, ty) || 1; tx /= l; ty /= l;
    let f = 1;
    if (i > 0 && i < pts.length - 1) {
      const ax = p.x - pts[i - 1].x, ay = p.y - pts[i - 1].y, al = Math.hypot(ax, ay) || 1;
      f = Math.min(1.8, 1 / Math.max(0.55, (-ay / al) * -ty + (ax / al) * tx));
    }
    const nx = -ty, ny = tx;
    for (const d of [offset + width / 2 * f, offset - width / 2 * f]) { const v = V3(p.x + nx * d, p.y + ny * d, h); pos.push(v.x, v.y, v.z); uvs.push(p.x + nx * d, p.y + ny * d); }
    if (i) { const k = 2 * i; idx.push(k - 2, k - 1, k + 1, k - 2, k + 1, k); }
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  g.setIndex(idx); g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat); m.receiveShadow = true; scene.add(m); return m;
}
function polygon(pts, h, mat) {
  const shape = new THREE.Shape(pts.map(p => new THREE.Vector2(p.x, p.y)));
  const g = new THREE.ShapeGeometry(shape); g.rotateX(-Math.PI / 2); g.translate(0, h, 0);
  const m = new THREE.Mesh(g, mat); m.receiveShadow = true; scene.add(m); return m;
}
function box(x, y, h, sx, sy, sz, mat, yaw = 0, parent = scene) {
  // sx along local x (yaw rotates it in the map plane), sy is height, sz across.
  const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), mat);
  m.position.copy(V3(x, y, h + sy / 2)); m.rotation.y = yaw; m.castShadow = m.receiveShadow = true; parent.add(m); return m;
}
function rod(a, b, r, seg = 6) {   // cylinder geometry between two three.js points
  const d = new THREE.Vector3().subVectors(b, a), g = new THREE.CylinderGeometry(r, r, d.length(), seg, 1, true);
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize()));
  g.translate((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2); return g.toNonIndexed();
}
const merged = (geos, mat) => { const m = new THREE.Mesh(mergeGeometries(geos.map(g => g.index ? g.toNonIndexed() : g)), mat); m.castShadow = m.receiveShadow = true; return m; };
function densify(pts, step = 1) {
  const out = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i], n = Math.max(1, Math.floor(Math.hypot(b.x - a.x, b.y - a.y) / step));
    for (let k = 1; k <= n; k++) out.push({ x: a.x + (b.x - a.x) * k / n, y: a.y + (b.y - a.y) * k / n });
  }
  return out;
}

// ---------------------------------------------------------------- facades
// Patterns read off Google Street View (2023-2024) for the buildings on the Ring.
const FACADES = {
  '238805703': { h: 19.5, wall: [214, 218, 220], seams: 1.1, plinth: [[132, 138, 142], 0, 0.5], tile: 3.3,
                 ribbons: [[2.0, 1.4], [6.2, 1.6], [10.6, 1.6], [15.0, 1.6]], glass: [118, 127, 134] },
  '194909084': { h: 14.5, wall: [224, 223, 216], tiles: true, tile: 3.3, ribbons: [[1.6, 2.4]], glass: [70, 82, 94],
                 punched: { z: [5.0, 8.3, 11.6], w: 1.7, h: 1.5 }, blind: [88, 122, 178] },
  '435095504': { h: 14.5, wall: [233, 231, 225], tile: 3.3, ribbons: [[1.5, 2.4], [5.0, 1.5], [8.4, 1.5], [11.8, 1.5]], glass: [84, 94, 104] },
  '32351024':  { h: 13.0, wall: [200, 204, 208], tiles: true, tile: 3.0, plinth: [[44, 47, 56], 0, 4.2], ribbons: [[5.6, 1.8], [9.2, 1.8]], glass: [112, 136, 160],
                 north: [-35, { h: 13.0, wall: [192, 197, 202], ribs: 0.5, tile: 3.0, ribbons: [[1.4, 2.2]], glass: [96, 106, 116] }] },
  '169986939': { h: 10.5, wall: [176, 181, 186], ribs: 0.5, tile: 3.0, ribbons: [[1.3, 2.2], [6.4, 2.0]], glass: [80, 90, 100], sign: [[98, 46, 56], 3.9, 0.9] },
  '169986942': { h: 8.5, wall: [200, 174, 124], bricks: true, tile: 2.8, punched: { z: [1.3, 4.3, 7.0], w: 1.3, h: 1.3 }, glass: [70, 78, 88], frame: [236, 236, 230] },
  '201943927': { h: 9.0, wall: [204, 180, 132], bricks: true, tile: 2.8, punched: { z: [1.3, 4.3, 7.0], w: 1.3, h: 1.3 }, glass: [70, 78, 88], frame: [236, 236, 230] },
};
const GENERIC = [[226, 226, 222], [212, 214, 214], [232, 228, 218], [200, 204, 206]];
const css = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;

function facadeTexture(f, h) {
  const ppm = 32, W = Math.round(f.tile * ppm), H = Math.round(h * ppm);
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H }), c = cv.getContext('2d');
  const Y = (z) => H - z * ppm;   // canvas y for height z (metres)
  c.fillStyle = css(f.wall); c.fillRect(0, 0, W, H);
  const line = (rgb, a) => { c.strokeStyle = `rgba(${rgb},${a})`; };
  if (f.seams) { line('90,100,108', 0.22); c.lineWidth = 1.5; for (let z = 1; z < h; z += f.seams) { c.beginPath(); c.moveTo(0, Y(z)); c.lineTo(W, Y(z)); c.stroke(); } }
  if (f.ribs) { for (let x = 0; x < W; x += f.ribs * ppm) { c.fillStyle = 'rgba(255,255,255,0.35)'; c.fillRect(x, 0, 3, H); c.fillStyle = 'rgba(40,50,60,0.18)'; c.fillRect(x + 4, 0, 3, H); } }
  if (f.tiles) { line('110,115,120', 0.16); c.lineWidth = 1; for (let z = 0; z < h; z += 0.6) { c.beginPath(); c.moveTo(0, Y(z)); c.lineTo(W, Y(z)); c.stroke(); }
    for (let x = 0; x < W; x += 0.6 * ppm) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, H); c.stroke(); } }
  if (f.bricks) { line('120,95,60', 0.2); c.lineWidth = 1; for (let z = 0, r = 0; z < h; z += 0.2, r++) { c.beginPath(); c.moveTo(0, Y(z)); c.lineTo(W, Y(z)); c.stroke();
    for (let x = (r % 2) * 0.13 * ppm; x < W; x += 0.26 * ppm) { c.beginPath(); c.moveTo(x, Y(z)); c.lineTo(x, Y(z + 0.2)); c.stroke(); } } }
  if (f.plinth) { const [rgb, z0, z1] = f.plinth; c.fillStyle = css(rgb); c.fillRect(0, Y(z1), W, (z1 - z0) * ppm); }
  if (f.sign) { const [rgb, z0, hb] = f.sign; c.fillStyle = css(rgb); c.fillRect(0, Y(z0 + hb), W, hb * ppm); }
  const glass = (x, z, w, hh) => {
    const g = c.createLinearGradient(0, Y(z + hh), 0, Y(z));
    const [r, gg, b] = f.glass; g.addColorStop(0, `rgb(${r + 40},${gg + 44},${b + 50})`); g.addColorStop(1, css(f.glass));
    c.fillStyle = g; c.fillRect(x, Y(z + hh), w, hh * ppm);
  };
  for (const [z0, hb] of f.ribbons || []) {
    if (z0 + hb > h - 0.4) continue;
    glass(0, z0, W, hb);
    c.fillStyle = 'rgba(225,230,235,0.85)'; for (let x = 0; x < W; x += 1.1 * ppm) c.fillRect(x, Y(z0 + hb), 3, hb * ppm);
    c.fillRect(0, Y(z0 + hb) - 2, W, 3);
  }
  if (f.punched) {
    const p = f.punched;
    for (const z of p.z) {
      if (z + p.h > h - 0.3) continue;
      const x = (W - p.w * ppm) / 2;
      if (f.frame) { c.fillStyle = css(f.frame); c.fillRect(x - 3, Y(z + p.h) - 3, p.w * ppm + 6, p.h * ppm + 6); }
      if (f.blind) { c.fillStyle = css(f.blind); c.fillRect(x, Y(z + p.h), p.w * ppm, p.h * ppm); c.fillStyle = 'rgba(255,255,255,0.18)';
        for (let yy = Y(z + p.h); yy < Y(z); yy += 5) c.fillRect(x, yy, p.w * ppm, 1); }
      else glass(x, z, p.w, p.h);
    }
  }
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace; t.wrapS = THREE.RepeatWrapping; t.anisotropy = 8;
  return t;
}

function building(id, pts, h, roofRGB, style) {
  // Walls with a per-building facade texture, u in metres along the perimeter.
  let ring = pts.slice(0, -1);
  const area = ring.reduce((s, p, i) => { const q = ring[(i + 1) % ring.length]; return s + p.x * q.y - q.x * p.y; }, 0);
  if (area < 0) ring.reverse();
  ring.push(ring[0]);
  const styles = [style, style.north && style.north[1]].filter(Boolean);
  const mats = styles.map(s => new THREE.MeshStandardMaterial({ map: facadeTexture(s, h), roughness: 0.75 }));
  const pos = [], uv = [], groups = [[], []];
  let u = 0;
  const edges = [];
  for (let i = 1; i < ring.length; i++) {
    const a = ring[i - 1], b = ring[i];
    if (style.north && (a.y - style.north[0]) * (b.y - style.north[0]) < 0) {
      const t = (style.north[0] - a.y) / (b.y - a.y), m = { x: a.x + (b.x - a.x) * t, y: style.north[0] };
      edges.push([a, m], [m, b]);
    } else edges.push([a, b]);
  }
  for (const [a, b] of edges) {
    const len = Math.hypot(b.x - a.x, b.y - a.y); if (len < 0.05) continue;
    const gi = style.north && (a.y + b.y) / 2 > style.north[0] ? 1 : 0;
    const tile = styles[gi].tile, u0 = u / tile, u1 = (u + len) / tile;
    const A0 = V3(a.x, a.y, 0), B0 = V3(b.x, b.y, 0), B1 = V3(b.x, b.y, h), A1 = V3(a.x, a.y, h);
    groups[gi].push([A0, B0, B1, A0, B1, A1], [[u0, 0], [u1, 0], [u1, 1], [u0, 0], [u1, 1], [u0, 1]]);
    u += len;
  }
  const g = new THREE.BufferGeometry();
  let start = 0;
  groups.forEach((list, gi) => {
    let count = 0;
    for (let k = 0; k < list.length; k += 2) { list[k].forEach(v => pos.push(v.x, v.y, v.z)); list[k + 1].forEach(t => uv.push(...t)); count += 6; }
    if (count) g.addGroup(start, count, gi); start += count;
  });
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  const walls = new THREE.Mesh(g, mats); walls.castShadow = walls.receiveShadow = true; scene.add(walls);
  const roof = polygon(ring, h, std(roofRGB ? srgb(...roofRGB) : srgb(150, 152, 150)));
  roof.castShadow = true;
  // A low parapet gives the flat roofs an edge.
  ribbon(ring, 0.35, h + 0.02, std(srgb(...style.wall).multiplyScalar(0.92)));
}

// ---------------------------------------------------------------- load data
const [osmText, roofJson] = await Promise.all([
  fetch(ASSETS + 'campus-map/source.osm').then(r => r.text()),
  fetch('roof-colors.json').then(r => r.json()),
]);
const xml = new DOMParser().parseFromString(osmText, 'application/xml');
const tagsOf = (el) => Object.fromEntries([...el.querySelectorAll('tag')].map(t => [t.getAttribute('k'), t.getAttribute('v')]));
const nodes = new Map();
for (const n of xml.querySelectorAll('node')) {
  nodes.set(n.getAttribute('id'), { x: (+n.getAttribute('lon') - LON0) * SX, y: (+n.getAttribute('lat') - LAT0) * SY, tags: tagsOf(n) });
}
const ways = [...xml.querySelectorAll('way')].map(w => ({ id: w.getAttribute('id'), tags: tagsOf(w),
  pts: [...w.querySelectorAll('nd')].map(nd => nodes.get(nd.getAttribute('ref'))).filter(Boolean) }));
const roofRGB = roofJson.rgb_by_osm_way;

// ---------------------------------------------------------------- ground, roads, buildings
// Surface textures in metres: grain, joints, and a few cracks, drawn once on canvases.
function surface(rgb, { size = 4, grain = 14, joints = 0, cracks = 0, tufts = false } = {}) {
  const N = 256, cv = Object.assign(document.createElement('canvas'), { width: N, height: N }), c = cv.getContext('2d'), r = rng(rgb[0] * 7 + size);
  c.fillStyle = css(rgb); c.fillRect(0, 0, N, N);
  for (let i = 0; i < 2600; i++) { const d = (r() - 0.5) * grain; c.fillStyle = `rgba(${d > 0 ? 255 : 0},${d > 0 ? 255 : 0},${d > 0 ? 255 : 0},${Math.abs(d) / 100})`;
    const sz = 1 + r() * 2.5; c.fillRect(r() * N, r() * N, sz, sz); }
  if (tufts) for (let i = 0; i < 500; i++) { c.fillStyle = r() < 0.5 ? 'rgba(60,90,30,0.25)' : 'rgba(170,190,90,0.22)'; c.fillRect(r() * N, r() * N, 2, 4 + r() * 4); }
  if (joints) { c.strokeStyle = 'rgba(60,60,55,0.28)'; c.lineWidth = 1.2; const st = N / (size / joints);
    for (let k = 0; k <= N; k += st) { c.beginPath(); c.moveTo(k, 0); c.lineTo(k, N); c.moveTo(0, k); c.lineTo(N, k); c.stroke(); } }
  for (let i = 0; i < cracks; i++) { c.strokeStyle = 'rgba(40,40,40,0.35)'; c.lineWidth = 1.4; c.beginPath(); let x = r() * N, y = r() * N; c.moveTo(x, y);
    for (let k = 0; k < 9; k++) { x += (r() - 0.5) * 40; y += (r() - 0.3) * 30; c.lineTo(x, y); } c.stroke(); }
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(1 / size, 1 / size); t.anisotropy = 8; return t;
}
const tex = (rgb, o) => new THREE.MeshStandardMaterial({ map: surface(rgb, o), roughness: 0.92 });
const M = {
  ground: tex([196, 196, 188], { size: 8, grain: 12 }), grass: tex([118, 150, 82], { size: 3, grain: 22, tufts: true }), bed: std(srgb(92, 120, 66)),
  asphalt: tex([128, 129, 128], { size: 6, grain: 18, cracks: 2 }), ring: tex([150, 150, 146], { size: 10, grain: 18, cracks: 4 }),
  sidewalk: tex([190, 189, 182], { size: 3, grain: 10, joints: 0.5 }),
  kerb: std(srgb(214, 212, 204)), pavers: tex([170, 168, 160], { size: 2, grain: 12, joints: 0.2 }), white: std(srgb(240, 240, 234)),
  yellow: std(srgb(242, 190, 30)), steel: std(srgb(180, 186, 188), { metalness: 0.5, roughness: 0.45 }),
  darkSteel: std(srgb(80, 86, 92), { metalness: 0.4, roughness: 0.5 }), concrete: std(srgb(200, 198, 190)),
  poly: new THREE.MeshStandardMaterial({ color: srgb(225, 236, 240), transparent: true, opacity: 0.32, roughness: 0.15, side: THREE.DoubleSide, depthWrite: false }),
  mesh: new THREE.MeshStandardMaterial({ color: srgb(120, 128, 132), transparent: true, opacity: 0.45, metalness: 0.4, side: THREE.DoubleSide, depthWrite: false }),
  free: new THREE.MeshStandardMaterial({ color: srgb(25, 194, 90), emissive: srgb(25, 194, 90), emissiveIntensity: 0.9 }),
  taken: new THREE.MeshStandardMaterial({ color: srgb(229, 50, 43), emissive: srgb(229, 50, 43), emissiveIntensity: 0.9 }),
};
const ground = new THREE.Mesh(new THREE.PlaneGeometry(2000, 2000), M.ground);
ground.rotation.x = -Math.PI / 2; ground.position.set(160, -0.02, 40); ground.receiveShadow = true; scene.add(ground);

for (const w of ways) {
  const t = w.tags, closed = w.pts.length > 3 && w.pts[0] === w.pts[w.pts.length - 1];
  if (!w.pts.some(inBox)) continue;
  if (closed && (t.landuse === 'grass' || t.landuse === 'meadow' || t.leisure === 'park')) polygon(w.pts, 0.02, M.grass);
  if (closed && t.amenity === 'parking') polygon(w.pts, 0.03, M.asphalt);
  if (t.highway && !['motorway', 'platform'].includes(t.highway)) {
    const isRing = (t.name || '').includes('Christoph Merian');
    const foot = ['footway', 'path', 'pedestrian', 'cycleway'].includes(t.highway);
    const wd = isRing ? 7.2 : ({ primary: 10, secondary: 8, tertiary: 7, residential: 5.8, service: 4.8 }[t.highway] || (foot ? 2 : 4.5));
    if (!foot) ribbon(w.pts, wd + 3.4, 0.05, M.sidewalk);
    ribbon(w.pts, wd, 0.09, isRing ? M.ring : foot ? M.sidewalk : M.asphalt);
  }
  if (closed && t.building && t.building !== 'roof') {
    const style = FACADES[w.id] || { h: 0, wall: GENERIC[+w.id % GENERIC.length], tile: 3.2, glass: [88, 100, 112],
      punched: { z: [1.2, 4.5, 7.8, 11.1, 14.4], w: 1.8, h: 1.5 } };
    let h = style.h || parseFloat(t.height) || (parseFloat(t['building:levels']) * 3.4) || 0;
    if (!h) { const ring = w.pts; const a = Math.abs(ring.reduce((s, p, i) => i ? s + ring[i - 1].x * p.y - p.x * ring[i - 1].y : s, 0)) / 2; h = 8 + Math.min(10, Math.sqrt(a) * 0.15); }
    building(w.id, w.pts, h, roofRGB[w.id], style);
  }
}

// The Ring between the stations, in travel order north -> south -> west.
const RING_IDS = ['1460188260', '1460188261', '1460188262', '1460188263', '1460188264', '1460188265', '1460188266', '1463696448', '1460188258'];
let ringLine = [];
for (const id of RING_IDS) for (const p of ways.find(w => w.id === id).pts)
  if (!ringLine.length || Math.hypot(p.x - ringLine.at(-1).x, p.y - ringLine.at(-1).y) > 0.05) ringLine.push(p);
const ringX = (y) => { const ns = ringLine.filter(p => p.y > -100);
  for (let i = 1; i < ns.length; i++) { const a = ns[i - 1], b = ns[i]; if ((y - a.y) * (y - b.y) <= 0) return a.x + (b.x - a.x) * (y - a.y) / ((b.y - a.y) || 1); }
  return ns.at(-1).x; };
const corridor = densify(ringLine);
const junctions = [];
for (const w of ways) if (w.tags.highway && !RING_IDS.includes(w.id))
  for (const p of [w.pts[0], w.pts.at(-1)]) if (p && ringLine.some(q => Math.hypot(p.x - q.x, p.y - q.y) < 1)) junctions.push(p);
const inLane = (p) => p.y > 2.5 && p.y < 58 && p.x > 150;
function kerb(side) {   // raised kerb runs, broken at side streets
  let run = [];
  const flush = () => { if (run.length > 1) { const k = ribbon(run, 0.24, 0.2, M.kerb); k.castShadow = true; } run = []; };
  corridor.forEach((p, i) => {
    if (junctions.some(j => Math.hypot(p.x - j.x, p.y - j.y) < 4.5)) return flush();
    const a = corridor[Math.max(0, i - 1)], b = corridor[Math.min(corridor.length - 1, i + 1)], l = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    const d = side > 0 ? (inLane(p) ? 6.75 : 3.75) : -3.75;
    run.push({ x: p.x - (b.y - a.y) / l * d, y: p.y + (b.x - a.x) / l * d });
  });
  flush();
}
kerb(1); kerb(-1);
const lanePts = corridor.filter(inLane);
ribbon(lanePts, 3.0, 0.085, M.ring, 5.15);

// ---------------------------------------------------------------- street furniture and markings
const paintBox = (x, y, sx, sz, mat, yaw = 0) => { const m = box(x, y, 0.1, sx, 0.012, sz, mat, yaw); m.castShadow = false; };
// Bruggrain bus stop: raised platform, yellow bus bay, BUS lettering.
box(149.0, 44.5, 0, 2.0, 0.2, 13.5, M.concrete, Math.PI / 2);
const bx = ringX(44.5) - 5.15;
paintBox(bx - 1.4, 44.5, 0.14, 13.8, M.yellow); paintBox(bx + 1.4, 44.5, 0.14, 13.8, M.yellow);
paintBox(bx, 37.6, 2.8, 0.14, M.yellow); paintBox(bx, 51.4, 2.8, 0.14, M.yellow);
// Perpendicular bays and the yellow zebra crossing at the south bend.
for (let k = 0; k < 24; k++) paintBox(162.15, -88 + k * 2.5, 3.7, 0.12, M.white);
for (let k = 0; k < 8; k++) paintBox(150.4, -88 + k * 2.5, 5, 0.12, M.white);
for (let k = 0; k < 18; k++) paintBox(70 + k * 2.5, -111.7, 0.12, 5, M.white);
for (let k = 0; k < 7; k++) paintBox(153.4 + k * 1.05, -101.5, 0.5, 4.0, M.yellow);
polygon([{ x: 101.5 - 31.5, y: -108.9 }, { x: 133, y: -108.9 }, { x: 133, y: -115.6 }, { x: 70, y: -115.6 }], 0.06, M.asphalt);
// Grass strip behind the north shelter and the wedge at the rounded corner.
polygon([{ x: 146.35, y: -2 }, { x: 153.2, y: -2 }, { x: 153.2, y: 2.5 }, { x: 150.3, y: 2.5 }, { x: 150.3, y: 37.5 }, { x: 148, y: 37.5 },
  { x: 148, y: 51.5 }, { x: 150.3, y: 51.5 }, { x: 150.3, y: 58.5 }, { x: 145.8, y: 58.5 }], 0.1, M.grass);
polygon([{ x: 132, y: -109.2 }, { x: 138.3, y: -108 }, { x: 142, y: -106 }, { x: 144.6, y: -103.4 }, { x: 145.5, y: -101.6 }, { x: 152.6, y: -100.5 },
  { x: 151.6, y: -106.5 }, { x: 148.3, y: -110.6 }, { x: 144.6, y: -113.3 }, { x: 139.5, y: -115.4 }, { x: 132, y: -115.4 }], 0.1, M.grass);
const island = []; for (let k = 0; k < 16; k++) island.push({ x: 149.6 + 2.3 * Math.cos(k * Math.PI / 8), y: 0.4 + 2.3 * Math.sin(k * Math.PI / 8) });
polygon(island, 0.3, M.bed);

// Smoking shelter at 35 Christoph Merian-Ring (Street View).
{ const sx = 117.8, sy = -110.15;
  box(sx, sy, 2.35, 3.7, 0.1, 2.4, M.steel); box(sx, sy + 1.15, 0, 3.6, 2.3, 0.04, M.poly); box(sx - 1.82, sy, 0, 0.04, 2.3, 2.3, M.poly); box(sx + 1.82, sy, 0, 0.04, 2.3, 2.3, M.poly);
  for (const dx of [-1.8, 1.8]) for (const dy of [-1.13, 1.13]) box(sx + dx, sy + dy, 0, 0.06, 2.4, 0.06, M.steel);
  box(sx - 0.6, sy + 0.7, 0.4, 1.8, 0.08, 0.4, M.darkSteel); }

// ---------------------------------------------------------------- bicycles
const BIKE_COLORS = [[20, 20, 22], [20, 20, 22], [20, 20, 22], [120, 124, 128], [120, 124, 128], [232, 232, 232], [232, 232, 232],
  [190, 30, 26], [30, 70, 160], [60, 110, 70], [235, 120, 20]].map(c => std(srgb(...c), { metalness: 0.3, roughness: 0.5 }));
const tyreMat = std(srgb(28, 28, 30));
const bikeTyres = (() => { const gs = [];
  for (const cx of [-0.52, 0.53]) { const t = new THREE.TorusGeometry(0.33, 0.028, 5, 14); t.translate(cx, 0.34, 0); gs.push(t.toNonIndexed()); }
  return mergeGeometries(gs); })();
const bikeFrame = (() => { const P = (x, z, l = 0) => new THREE.Vector3(x, z, l);
  const segs = [[P(-0.52, 0.34), P(-0.05, 0.3)], [P(-0.05, 0.3), P(-0.2, 0.85)], [P(-0.52, 0.34), P(-0.2, 0.82)], [P(-0.2, 0.82), P(0.4, 0.8)],
    [P(-0.05, 0.3), P(0.42, 0.68)], [P(0.42, 0.68), P(0.4, 0.84)], [P(0.42, 0.68), P(0.53, 0.34)], [P(0.4, 0.84), P(0.36, 1.0)],
    [P(0.36, 1.0, -0.3), P(0.36, 1.0, 0.3)], [P(-0.32, 0.9), P(-0.1, 0.9)]];
  return mergeGeometries(segs.map(([a, b]) => rod(a, b, 0.024, 5))); })();
const rand = rng(5), pick = rng(29);
function bike(x, y, h, heading, lean) {
  const g = new THREE.Group();
  const frame = new THREE.Mesh(bikeFrame, BIKE_COLORS[Math.floor(pick() * BIKE_COLORS.length)]), tyres = new THREE.Mesh(bikeTyres, tyreMat);
  frame.castShadow = tyres.castShadow = true; g.add(frame, tyres);
  g.position.copy(V3(x, y, h)); g.rotation.set(lean, Math.atan2(heading.y, heading.x), 0, 'YXZ'); scene.add(g);
}
const stations = { CMR_NORTH_01: { free: 0, total: 0 }, CMR_SOUTH_02: { free: 0, total: 0 } };
function slot(zone, x, y, h, heading, width, taken, rack) {
  const pad = new THREE.Mesh(new THREE.BoxGeometry(1.9, 0.02, width), taken ? M.taken : M.free);
  pad.position.copy(V3(x, y, h + 0.012)); pad.rotation.y = Math.atan2(heading.y, heading.x); pad.receiveShadow = true; scene.add(pad);
  stations[zone].total++; if (!taken) { stations[zone].free++; return; }
  // Real parking is messy: skewed, pushed in or left out, leaning on kickstands, sometimes across two spots.
  const gauss = () => (rand() + rand() + rand() - 1.5) * 0.8;
  let turn = gauss() * (rack ? 0.07 : 0.24); if (!rack && rand() < 0.15) turn += (rand() < 0.5 ? -1 : 1) * 0.6;
  const side = (rand() - 0.5) * (rack ? 0.1 : 0.36), push = rack ? rand() * 0.25 - 0.15 : rand() * 0.65 - 0.35;
  const c = Math.cos(turn), s = Math.sin(turn), hd = { x: heading.x * c - heading.y * s, y: heading.x * s + heading.y * c };
  bike(x + heading.x * push - heading.y * side, y + heading.y * push + heading.x * side, h, hd,
       rack ? 0 : (rand() < 0.5 ? -1 : 1) * (0.12 + rand() * 0.1));
}

// ---------------------------------------------------------------- north station
// 53 m galvanised shelter from OSM way 1463536691: corrugated roof, nine bays,
// paired posts on concrete sills, mesh end panels. Faces the parking aisle.
const roofWay = ways.find(w => w.id === '1463536691').pts.slice(0, -1);
const cy = roofWay.reduce((s, p) => s + p.y, 0) / roofWay.length;
const southE = roofWay.filter(p => p.y < cy), northE = roofWay.filter(p => p.y > cy);
const O = { x: (southE[0].x + southE[1].x) / 2, y: (southE[0].y + southE[1].y) / 2 };
const N = { x: (northE[0].x + northE[1].x) / 2, y: (northE[0].y + northE[1].y) / 2 };
const L = Math.hypot(N.x - O.x, N.y - O.y), U = { x: (N.x - O.x) / L, y: (N.y - O.y) / L }, Vb = { x: U.y, y: -U.x };
const NP = (s, t) => ({ x: O.x + U.x * s + Vb.x * t, y: O.y + U.y * s + Vb.y * t });
{
  const grp = new THREE.Group(); grp.position.copy(V3(O.x, O.y)); grp.rotation.y = Math.atan2(U.y, U.x); scene.add(grp);
  const L3 = (s, h, t) => new THREE.Vector3(s, h, t);   // local: x along roof, z towards the back (east)
  const eave = (t) => 2.55 - 0.06 * (t + 1.25);
  const floor = new THREE.Mesh(new THREE.BoxGeometry(L + 0.6, 0.16, 2.75), M.pavers); floor.position.set(L / 2, 0.08, -0.03); floor.receiveShadow = true; grp.add(floor);
  const edge = new THREE.Mesh(new THREE.BoxGeometry(L + 0.6, 0.012, 0.2), M.white); edge.position.set(L / 2, 0.166, -1.3); grp.add(edge);
  const tubes = [], bounds = Array.from({ length: 10 }, (_, k) => L * k / 9);
  bounds.forEach((s, k) => {
    const pair = k === 0 ? [0.12, 0.47] : k === 9 ? [L - 0.47, L - 0.12] : [s - 0.18, s + 0.18];
    for (const sp of pair) for (const t of [-1, 1]) tubes.push(rod(L3(sp, 0.16, t), L3(sp, eave(t) - 0.1, t), 0.045, 4));
    pair.forEach((sp, i) => { const e = sp + (i ? 0.85 : -0.85); if (e > 0 && e < L) tubes.push(rod(L3(sp, 1.3, 1), L3(e, 0.55, 1), 0.022)); });
    const sill = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.2, 2.3), M.concrete); sill.position.set(Math.min(Math.max(s, 0.3), L - 0.3), 0.26, 0); sill.castShadow = sill.receiveShadow = true; grp.add(sill);
    tubes.push(rod(L3(s, eave(-1.25) - 0.1, -1.25), L3(s, eave(1.25) - 0.1, 1.25), 0.05, 4));
  });
  for (const t of [-1, -0.35, 0.35, 1]) tubes.push(rod(L3(0, eave(t) - 0.07, t), L3(L, eave(t) - 0.07, t), 0.04, 4));
  tubes.push(rod(L3(0.12, 0.55, 1), L3(L - 0.12, 0.55, 1), 0.025));
  grp.add(merged(tubes, M.steel));
  // Corrugated sheet: a ridged strip across the roof width.
  const pos = []; let i = 0;
  for (let s = -0.05; s <= L + 0.05; s += 0.05, i++) { const lift = i % 4 === 1 || i % 4 === 2 ? 0.035 : 0; for (const t of [-1.25, 1.25]) pos.push(s, eave(t) + lift, t); }
  const idx = []; for (let k = 1; k < pos.length / 6; k++) { const a = 2 * (k - 1); idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  const sheetG = new THREE.BufferGeometry(); sheetG.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); sheetG.setIndex(idx); sheetG.computeVertexNormals();
  const sheet = new THREE.Mesh(sheetG, std(srgb(170, 176, 178), { metalness: 0.4, roughness: 0.5, side: THREE.DoubleSide })); sheet.castShadow = sheet.receiveShadow = true; grp.add(sheet);
  for (const t of [-1.27, 1.27]) { const f = new THREE.Mesh(new THREE.BoxGeometry(L + 0.1, 0.26, 0.05), M.steel); f.position.set(L / 2, eave(t) + 0.02, t); f.castShadow = true; grp.add(f); }
  for (const s of [0.02, L - 0.02]) { const p = new THREE.Mesh(new THREE.BoxGeometry(0.03, 2.1, 2.0), M.mesh); p.position.set(s, 1.3, 0); grp.add(p); }
  for (let k = 0; k < 9; k++) { const l = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.012, 2.3), M.white); l.position.set((bounds[k] + bounds[k + 1]) / 2, 0.166, -0.1); grp.add(l); }
  const sr = rng(11);
  for (let k = 0; k < 9; k++) for (let j = 0; j < 5; j++) { const p = NP(bounds[k] + 0.95 + j, 0); slot('CMR_NORTH_01', p.x, p.y, 0.16, Vb, 0.7, sr() < 0.55, false); }
}

// ---------------------------------------------------------------- south station
// Curved clear-roof shelters with high-low front-wheel racks (site photos).
function curvedShelter(origin, U2, occupied) {
  // origin: back corner on the facade line; U2 runs along it, the facade is on its right.
  const back = { x: U2.y, y: -U2.x }, grp = new THREE.Group();
  grp.position.copy(V3(origin.x, origin.y)); grp.rotation.y = Math.atan2(U2.y, U2.x); scene.add(grp);
  const prof = []; for (let a = 120; a >= 0; a -= 10) prof.push([-0.45 + 1.5 * Math.cos(a * Math.PI / 180) - 1.05, 0.25 + 2.0 * Math.sin(a * Math.PI / 180)]);
  const P = (s, t, h) => new THREE.Vector3(s, h, t);   // t: 0 at the back, negative towards the street
  const span = 5, tubes = [];
  for (let i = 0; i < 5; i++) { const s = i * span / 4; for (let k = 1; k < prof.length; k++) tubes.push(rod(P(s, prof[k - 1][0], prof[k - 1][1]), P(s, prof[k][0], prof[k][1]), 0.03)); tubes.push(rod(P(s, 0, 0.25), P(s, 0, 0), 0.03)); }
  for (const s of [0, span]) { tubes.push(rod(P(s, -2.25, 0), P(s, -2.25, 1.98), 0.04, 4)); tubes.push(rod(P(s, -2.25, 0.08), P(s, 0, 0.08), 0.025)); }
  for (const k of [0, 3, 6, prof.length - 1]) tubes.push(rod(P(0, prof[k][0], prof[k][1]), P(span, prof[k][0], prof[k][1]), 0.028));
  for (const t of [-1.0, -0.25]) tubes.push(rod(P(0.1, t, 0.06), P(span - 0.1, t, 0.06), 0.02));
  for (let k = 0; k < 10; k++) { const s = 0.25 + k * 0.5, hh = k % 2 ? 0.62 : 0.42;
    for (const w of [-0.035, 0.035]) { const q = [P(s + w, -0.25, 0.06), P(s + w, -0.39, hh), P(s + w, -0.83, hh * 0.6), P(s + w, -1.0, 0.06)];
      for (let j = 1; j < 4; j++) tubes.push(rod(q[j - 1], q[j], 0.012, 4)); } }
  grp.add(merged(tubes, M.steel));
  const pos = [];
  for (let k = 1; k < prof.length; k++) { const [t0, h0] = prof[k - 1], [t1, h1] = prof[k];
    pos.push(0, h0 + 0.03, t0, span, h0 + 0.03, t0, span, h1 + 0.03, t1, 0, h0 + 0.03, t0, span, h1 + 0.03, t1, 0, h1 + 0.03, t1); }
  for (const s of [0, span]) { const ring = [[-2.25, 0.08], ...prof, [0, 0.08]]; const cx = ring.reduce((a, p) => a + p[0], 0) / ring.length, cz = ring.reduce((a, p) => a + p[1], 0) / ring.length;
    for (let k = 0; k < ring.length; k++) { const a = ring[k], b = ring[(k + 1) % ring.length]; pos.push(s, cz, cx, s, a[1], a[0], s, b[1], b[0]); } }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals();
  grp.add(new THREE.Mesh(g, M.poly));
  for (let k = 0; k < 10; k++) {
    const s = 0.25 + k * 0.5;   // slot centre 1.13 m out from the facade, bikes face into the rack
    slot('CMR_SOUTH_02', origin.x + U2.x * s - back.x * 1.13, origin.y + U2.y * s - back.y * 1.13, 0.07, back, 0.42, occupied.includes(k), true);
  }
}
// Street View: one west of the rounded corner facing the Ring; the second
// (photo 083823) on the east facade beside the Ring, position unverified.
curvedShelter({ x: 130.4, y: -108.9 }, { x: -1, y: 0 }, [0, 1, 2, 3, 5, 6, 8]);
curvedShelter({ x: 145.7, y: -94.0 }, { x: 0, y: -1 }, [1, 2, 4, 7]);

// ---------------------------------------------------------------- Kenney models
const loader = new GLTFLoader();
const glb = {};
async function model(kit, name) { return glb[name] ??= (await loader.loadAsync(`kenney/${kit}/${name}.glb`)).scene; }
const CROWN = { green: srgb(84, 134, 60), yellowing: srgb(150, 156, 62), plane: srgb(70, 116, 52), beech: srgb(110, 48, 58) };
const BARK = srgb(110, 88, 70), SHRUB = srgb(78, 118, 62);
async function place(kit, name, x, y, h, yaw, scale, opts = {}) {
  const o = (await model(kit, name)).clone(true);
  o.traverse(c => { if (!c.isMesh) return; c.castShadow = c.receiveShadow = true;
    const n = c.material.name || '';
    if (opts.crown && n.startsWith('leafs')) c.material = std(CROWN[opts.crown]);
    else if (n.startsWith('wood')) c.material = std(BARK);
    else if (n.startsWith('grass')) c.material = std(SHRUB);
    else if (opts.paint) c.material = opts.paint; });
  o.position.copy(V3(x, y, h)); o.rotation.y = yaw; o.scale.setScalar(scale); scene.add(o); return o;
}
// Car paint: grey the Kenney palette texture, then tint it with a real paint colour.
const paintCache = {};
function carPaint(base, rgb, value) {
  const key = rgb.join() + value; if (paintCache[key]) return paintCache[key];
  const m = base.clone(); m.color = srgb(...rgb); m.roughness = 0.4; m.metalness = 0.25;
  m.onBeforeCompile = (sh) => { sh.fragmentShader = sh.fragmentShader.replace('#include <map_fragment>',
    `#ifdef USE_MAP\n vec4 tx = texture2D(map, vMapUv); diffuseColor.rgb *= vec3(dot(tx.rgb, vec3(0.299,0.587,0.114)) * ${value.toFixed(2)});\n#endif`); };
  m.customProgramCacheKey = () => 'paint' + key;
  return paintCache[key] = m;
}
const PAINTS = [[[245, 245, 242], 1.7, 25], [[255, 255, 255], 0.22, 22], [[205, 210, 216], 1.15, 20], [[150, 152, 156], 0.8, 12],
  [[200, 30, 26], 1.3, 10], [[40, 62, 120], 1.1, 7], [[130, 110, 90], 1.1, 4]];
const crand = rng(30), CARS = ['sedan', 'suv', 'hatchback-sports', 'van', 'sedan', 'suv', 'delivery'];
const jobs = [];
function car(x, y, yaw, fill) {
  if (crand() > fill) return;
  let r = crand() * 100, p = PAINTS[0]; for (const q of PAINTS) { if ((r -= q[2]) < 0) { p = q; break; } }
  const name = CARS[Math.floor(crand() * CARS.length)], jitter = (crand() - 0.5) * 0.08;
  jobs.push(model('car-kit', name).then(src => { let base; src.traverse(c => { if (c.isMesh && !base) base = c.material; });
    return place('car-kit', name, x, y, 0.09, yaw + jitter, 1.75, { paint: carPaint(base, p[0], p[1]) }); }));
}
for (const y of [35, 55]) car(ringX(y) - 5.15, y, 0, 1);
const planeYs = [0, 4, 8, 12, 16, 20].map(k => -88 + k * 2.5);
for (let k = 0; k < 23; k++) { const y = -88 + 1.25 + k * 2.5; if (planeYs.every(py => Math.abs(y - py) > 1.5)) car(162.1, y, Math.PI / 2, 0.6); }
for (let k = 0; k < 7; k++) car(150.4, -88 + 1.25 + k * 2.5, Math.PI / 2, 0.7);
for (let k = 0; k < 17; k++) car(70 + 1.25 + k * 2.5, -111.7, 0, 0.7);
for (const cx of [132.0, 137.2]) for (let k = 0; k < 23; k++) car(cx, -1.5 + k * 2.7, Math.PI / 2 + 0.45, 0.5);

const prand = rng(7), spin = () => prand() * Math.PI * 2;
jobs.push(place('nature-kit', 'tree_default_fall', 149.6, 0.4, 0.3, 0.4, 4.4, { crown: 'green' }));
for (const y of [8, 20, 31, 56]) jobs.push(place('nature-kit', 'tree_default_fall', 148.6, y, 0.1, spin(), 3.9, { crown: 'green' }));
for (const y of [5, 10.5, 16, 21.5, 27, 32.5, 54]) { jobs.push(place('nature-kit', prand() < 0.5 ? 'plant_bushLarge' : 'plant_bushDetailed', 147.3, y, 0.1, spin(), 4.2));
  jobs.push(place('nature-kit', 'grass_large', 147.4, y + 2.6, 0.1, spin(), 2.2)); }
for (const y of [-86, -78.5, -71, -21]) jobs.push(place('nature-kit', 'tree_default_fall', 147.4, y, 0.1, spin(), 3.4, { crown: 'yellowing' }));
for (const y of planeYs) jobs.push(place('nature-kit', 'tree_oak_fall', 163.4, y, 0.1, spin(), 7.5, { crown: 'plane' }));
for (const x of [121, 128.5, 136, 141.5]) jobs.push(place('nature-kit', 'tree_fat_fall', x, -125.2, 0.1, spin(), 5.6, { crown: 'beech' }));
for (const [x, y] of [[148, -102.8], [144.2, -107.6], [140.2, -111]]) jobs.push(place('nature-kit', 'tree_default_fall', x, y, 0.1, spin(), 3.6, { crown: 'yellowing' }));
for (const [x, y, n] of [[136, -112, 'plant_bushLarge'], [140.5, -110.2, 'plant_bushDetailed'], [144, -107, 'plant_bushLarge']]) jobs.push(place('nature-kit', n, x, y, 0.1, spin(), 4.4));
for (const n of nodes.values()) if (n.tags.natural === 'tree' && inBox(n)) jobs.push(place('nature-kit', 'tree_default_fall', n.x, n.y, 0, spin(), 4.2, { crown: 'green' }));
for (const y of [8, 33, -25, -50, -75, -95]) jobs.push(place('city-kit-roads', 'light-curved', ringX(y) - (y > 2.5 && y < 58 ? 7.15 : 4.3), y, 0.1, -Math.PI / 2, 9));
for (const x of [98, 110, 141]) jobs.push(place('city-kit-roads', 'light-curved', x, -115.9, 0.1, Math.PI, 9));
jobs.push(place('city-kit-roads', 'road-sign-empty', 148.5, 39, 0.2, 0, 5.5).then(() => box(148.5, 39, 2.5, 0.04, 0.55, 0.55, M.yellow)));
await Promise.all(jobs);

// ---------------------------------------------------------------- station labels
const stationLabels = [];
function label(zone, x, y, h, title) {
  const s = stations[zone], el = document.createElement('div'); el.className = 'station-label';
  el.innerHTML = `${title}<br><span class="count">${s.free}</span> <span class="of">free of ${s.total}</span>`;
  const o = new CSS2DObject(el); o.position.copy(V3(x, y, h)); scene.add(o); stationLabels.push(o);
}
const northMid = NP(L / 2, 0);
label('CMR_NORTH_01', northMid.x, northMid.y, 4.2, 'North stand');
label('CMR_SOUTH_02', 127.9, -110.2, 3.6, 'South stand');

// ---------------------------------------------------------------- cameras
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.49; controls.enabled = false;
const route = [...ringLine].reverse().filter(p => p.y < 66 && p.x > 108);
const rideLine = densify(route, 2).map((p, i, a) => {   // keep right: 1.4 m right of the centre line
  const q = a[Math.min(a.length - 1, i + 1)], o = a[Math.max(0, i - 1)], l = Math.hypot(q.x - o.x, q.y - o.y) || 1;
  return V3(p.x + (q.y - o.y) / l * 1.4, p.y - (q.x - o.x) / l * 1.4, 1.65);
});
const ride = new THREE.CatmullRomCurve3(rideLine, false, 'centripetal');
const rideLen = ride.getLength();
const stops = [{ at: V3(northMid.x, northMid.y, 0.6) }, { at: V3(128, -110, 0.6) }];
let mode = 'ride', u = 0;
const VIEWS = {
  north: [V3(ringX(6) - 2, 6, 1.65), V3(NP(24, 0.6).x, NP(24, 0.6).y, 0.4)],
  south: [V3(135.5, -117.6, 1.65), V3(122.5, -110, 0.5)],
  free: [V3(215, -120, 95), V3(145, -40, 0)],
};
function setMode(m) {
  mode = m; document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('on', b.dataset.view === m));
  controls.enabled = m !== 'ride';
  if (m === 'ride') { u = 0; return; }
  camera.position.copy(VIEWS[m][0]); controls.target.copy(VIEWS[m][1]); controls.update();
}
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.view)));
const look = new THREE.Vector3(), clock = new THREE.Clock();
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (mode === 'ride') {
    const p = ride.getPointAt(u);
    const near = Math.min(...stops.map(s => s.at.distanceTo(p)));
    const speed = THREE.MathUtils.lerp(2.2, 6.5, THREE.MathUtils.smoothstep(near, 8, 30));   // slow down at the stands
    u += speed * dt / rideLen; if (u >= 1) u = 0;
    camera.position.copy(p);
    look.copy(ride.getPointAt(Math.min(1, u + 12 / rideLen)));
    for (const s of stops) { const w = 1 - THREE.MathUtils.smoothstep(s.at.distanceTo(p), 6, 28); look.lerp(s.at, w * 0.75); }
    camera.lookAt(look);
  } else controls.update();
  // Show a stand's label only once it is close enough to matter.
  for (const o of stationLabels) o.element.style.opacity = mode === 'free' || o.position.distanceTo(camera.position) < 70 ? '1' : '0';
  composer.render(); labels.render(scene, camera);
  requestAnimationFrame(frame);
}
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight); labels.setSize(innerWidth, innerHeight);
});
document.getElementById('loading').remove();
window.__ring = { stations, setMode };   // handy for checks and for wiring live data later
setMode('ride');
frame();
