"""Write the standalone HTML: scene JSON + vendored three.js (MIT) + a small orbit viewer, all inline."""
from __future__ import annotations
import html, json
from pathlib import Path

VENDOR = Path(__file__).parent / "vendor"

# Scene construction is kept free of DOM/WebGL so it can be run under node (see tests).
SCENE_JS = r"""
export function buildScene(THREE, scene, data) {
  const group = new THREE.Group();
  const meshes = [];
  for (const p of data.parts) {
    let geo;
    if (p.shape === 'box') geo = new THREE.BoxGeometry(p.size[0], p.size[1], p.size[2]);
    else if (p.shape === 'sphere') geo = new THREE.SphereGeometry(p.radius, 32, 20);
    else if (p.shape === 'cylinder') geo = new THREE.CylinderGeometry(p.radius, p.radius, p.height, 32);
    else if (p.shape === 'cone') geo = new THREE.ConeGeometry(p.radius, p.height, 32);
    else throw new Error('unknown shape ' + p.shape);
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: p.color, roughness: 0.6, metalness: 0.1 }));
    m.position.set(p.position[0], p.position[1], p.position[2]);
    const d = Math.PI / 180;
    m.rotation.set(p.rotation[0] * d, p.rotation[1] * d, p.rotation[2] * d);
    m.userData = { id: p.id, label: p.label };
    group.add(m); meshes.push(m);
  }
  scene.add(group);
  return { group, meshes };
}
export function frame(data) {
  const b = data.bounds, c = b.min.map((v, i) => (v + b.max[i]) / 2);
  const r = Math.max(1e-6, Math.hypot(b.size[0], b.size[1], b.size[2]) / 2);
  return { center: c, radius: r };
}
"""

VIEW_JS = r"""
const data = JSON.parse(document.getElementById('scene').textContent);
const src = document.getElementById('three-src').textContent;
const url = URL.createObjectURL(new Blob([src], { type: 'text/javascript' }));
const THREE = await import(url);
const sceneMod = await import(URL.createObjectURL(new Blob([document.getElementById('scene-js').textContent], { type: 'text/javascript' })));
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x14181d);
const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1e7);
scene.add(new THREE.HemisphereLight(0xffffff, 0x333344, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(3, 5, 4); scene.add(sun);
const { meshes } = sceneMod.buildScene(THREE, scene, data);
const f = sceneMod.frame(data);
const grid = new THREE.GridHelper(f.radius * 4, 20, 0x556070, 0x2a3038); grid.position.set(f.center[0], data.bounds.min[1], f.center[2]); scene.add(grid);
let yaw = 0.8, pitch = 0.45, dist = f.radius * 3.2;
const target = new THREE.Vector3(f.center[0], f.center[1], f.center[2]);
function place() {
  camera.position.set(target.x + dist * Math.cos(pitch) * Math.sin(yaw), target.y + dist * Math.sin(pitch), target.z + dist * Math.cos(pitch) * Math.cos(yaw));
  camera.lookAt(target);
}
function resize() { const w = canvas.clientWidth, h = canvas.clientHeight; renderer.setPixelRatio(devicePixelRatio); renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
let drag = null;
canvas.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, moved: false }; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointermove', e => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true;
  yaw -= dx * 0.008; pitch = Math.max(-1.5, Math.min(1.5, pitch + dy * 0.008)); drag.x = e.clientX; drag.y = e.clientY;
});
canvas.addEventListener('pointerup', e => {
  const was = drag; drag = null;
  if (was && !was.moved) pick(e);
});
canvas.addEventListener('wheel', e => { e.preventDefault(); dist = Math.max(f.radius * 0.3, Math.min(f.radius * 30, dist * Math.exp(e.deltaY * 0.001))); }, { passive: false });
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2(); let sel = null;
function pick(e) {
  const r = canvas.getBoundingClientRect();
  ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const hit = ray.intersectObjects(meshes)[0];
  if (sel) sel.material.emissive.setHex(0x000000);
  sel = hit ? hit.object : null;
  if (sel) sel.material.emissive.setHex(0x333333);
  document.getElementById('sel').textContent = sel ? sel.userData.label + ' (' + sel.userData.id + ')' : 'click a part';
}
function loop() { resize(); place(); renderer.render(scene, camera); requestAnimationFrame(loop); }
loop();
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<style>html,body{margin:0;height:100%%;background:#14181d;color:#dde3ea;font:14px system-ui,sans-serif}
#c{width:100%%;height:100%%;display:block;touch-action:none}
#hud{position:fixed;left:12px;top:12px;background:rgba(20,24,29,.85);padding:10px 14px;border-radius:6px;max-width:320px}
#hud h1{font-size:16px;margin:0 0 4px}#hud small{color:#9aa6b2}</style></head>
<body><canvas id="c"></canvas>
<div id="hud"><h1>%(title)s</h1><small>%(summary)s</small><br><small>drag = orbit, wheel = zoom, click = select</small><div id="sel">click a part</div></div>
<script id="scene" type="application/json">%(scene)s</script>
<script id="scene-js" type="text/plain">%(scene_js)s</script>
<script id="three-src" type="text/plain">%(three)s</script>
<script type="module">%(view)s</script>
</body></html>
"""


def _safe(s: str) -> str:
    return s.replace("</", "<\\/")


def render(scene: dict) -> str:
    title = html.escape(scene["name"])
    u = (" " + html.escape(scene["units"])) if scene["units"] else ""
    sz = scene["bounds"]["size"]
    summary = "%d parts; extent %s x %s x %s%s" % (len(scene["parts"]), *(("%g" % round(v, 4)) for v in sz), u)
    three = (VENDOR / "three.module.min.js").read_text(encoding="utf-8")
    return PAGE % {"title": title, "summary": summary, "scene": _safe(json.dumps(scene)), "scene_js": _safe(SCENE_JS),
                   "three": _safe(three), "view": VIEW_JS}
