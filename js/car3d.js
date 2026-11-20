/* CARS Auto Center · carro 3D do pré-diagnóstico (three.js).
   Modelo: models/carro.glb, gerado no Blender por 3d/carro.py, com um objeto por sistema.
   Interface: recebe cars:select (lista de áreas) e devolve cars:picked (toque no carro). */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const D = window.CARS_DATA;
const reduce = document.documentElement.classList.contains('reduce');
const gsap = window.gsap;
const stage = document.querySelector('[data-stage]');
const canvas = document.querySelector('[data-canvas]');
const hotLayer = document.querySelector('[data-hotspots]');
const loading = document.querySelector('[data-loading]');
const hint = document.querySelector('[data-hint]');
const xrayBtn = document.querySelector('[data-xray]');

const PREFIX = {
  motor: ['motor_'], correia: ['correia_'], cambio: ['cambio_'], bateria: ['bateria_'],
  arrefecimento: ['arrefecimento_'], freios: ['freio_'], suspensao: ['susp_'],
  pneus: ['pneu_', 'roda_'], escape: ['escape_'], iluminacao: ['luz_']
};
const SHELL = ['carroceria', 'cabine', 'espelho', 'ma', 'grade', 'placa'];
const SPIN = ['pneu_', 'roda_', 'freio_disco_'];
const RED = new THREE.Color('#ff3326');

function fallback(msg) {
  loading.hidden = true;
  canvas.hidden = true;
  document.querySelector('[data-fallback]').hidden = false;
  document.querySelectorAll('.diag__tools .tool').forEach((b) => { b.disabled = true; });
  if (hint) hint.textContent = msg || 'Escolha a área na lista ao lado.';
}

function webglOK() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
  } catch (e) { return false; }
}

let started = false;
function boot() {
  if (started) return;
  started = true;
  if (!webglOK()) { fallback('Seu navegador não abriu o 3D. Escolha a área na lista.'); return; }
  try { init(); } catch (e) { console.error(e); fallback(); }
}

// carrega só quando a seção chega perto da tela
const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); boot(); } }, { rootMargin: '900px 0px' });
io.observe(stage);

function init() {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.85;

  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 80);
  const HOME = { pos: new THREE.Vector3(5.0, 1.95, 4.6), target: new THREE.Vector3(0, 0.5, 0) };
  camera.position.copy(HOME.pos);

  const key = new THREE.DirectionalLight(0xffffff, 1.7);
  key.position.set(4, 6, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xff3a2a, 2.2);
  rim.position.set(-5, 2.5, -4);
  scene.add(rim);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x221111, 0.35));

  // chão: sombra de contato + anel do elevador
  const sc = document.createElement('canvas');
  sc.width = sc.height = 256;
  const g = sc.getContext('2d');
  const grad = g.createRadialGradient(128, 128, 10, 128, 128, 128);
  grad.addColorStop(0, 'rgba(0,0,0,0.85)');
  grad.addColorStop(0.55, 'rgba(0,0,0,0.45)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 256, 256);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(5.6, 2.8), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.002;
  scene.add(shadow);
  const ring = new THREE.Mesh(new THREE.RingGeometry(2.95, 2.97, 128), new THREE.MeshBasicMaterial({ color: 0xff3326, transparent: true, opacity: 0.55 }));
  ring.rotation.x = -Math.PI / 2;
  scene.add(ring);
  const ring2 = new THREE.Mesh(new THREE.RingGeometry(3.25, 3.255, 128), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.12 }));
  ring2.rotation.x = -Math.PI / 2;
  scene.add(ring2);

  const controls = new OrbitControls(camera, canvas);
  controls.target.copy(HOME.target);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enablePan = false;
  controls.minDistance = 2.4;
  controls.maxDistance = 11;
  controls.maxPolarAngle = Math.PI * 0.53;
  controls.autoRotate = !reduce;
  controls.autoRotateSpeed = 0.55;
  controls.update();
  // no celular: arrastar na horizontal gira, na vertical rola a página
  canvas.style.touchAction = 'pan-y';

  const zoneMeshes = {};      // id -> [mesh]
  const shellMats = [];
  const spinners = [];
  const pickables = [];
  const anchors = {};
  let car = null;

  function zoneOf(name) {
    for (const id in PREFIX) if (PREFIX[id].some((p) => name.startsWith(p))) return id;
    return null;
  }
  function rootName(o) {
    // primitivas de objetos com mais de um material viram filhos sem nome próprio
    let n = o;
    while (n && n.parent && n.parent !== car && !n.name) n = n.parent;
    return (n && n.name) || '';
  }

  const loader = new GLTFLoader();
  loader.load('models/carro.glb', (gltf) => {
    car = gltf.scene;
    car.traverse((o) => {
      if (!o.isMesh) return;
      const name = o.name.match(/^(Mesh|Object)\d*$/) ? rootName(o.parent) : (o.name || rootName(o));
      const n2 = rootName(o) || name;
      const id = zoneOf(n2) || zoneOf(name);
      o.material = o.material.clone();
      o.userData.base = { emissive: o.material.emissive ? o.material.emissive.clone() : null, ei: o.material.emissiveIntensity || 0 };
      if (id) {
        (zoneMeshes[id] = zoneMeshes[id] || []).push(o);
        o.userData.zone = id;
        pickables.push(o);
      } else if (SHELL.some((s) => n2.startsWith(s))) {
        o.userData.shell = true;
        shellMats.push(o.material);
        pickables.push(o);
      }
    });
    car.traverse((o) => {
      if (SPIN.some((s) => o.name.startsWith(s))) spinners.push(o);
      D.zones.forEach((z) => { if (o.name === z.anchor) anchors[z.id] = o; });
    });
    scene.add(car);
    loading.hidden = true;
    buildHotspots();
    resize();
    start();
    if (pending) select(pending);
  }, undefined, (err) => { console.error(err); fallback(); });

  /* ------------------------------------------------ pontos clicáveis (botões HTML) */
  const hot = {};
  function buildHotspots() {
    D.zones.forEach((z, i) => {
      if (!anchors[z.id]) return;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'hot';
      b.dataset.id = z.id;
      b.innerHTML = '<i></i><span>' + String(i + 1).padStart(2, '0') + ' · ' + z.name + '</span>';
      b.tabIndex = -1;            // pelo teclado, a lista de áreas faz o mesmo
      b.setAttribute('aria-hidden', 'true');
      b.addEventListener('click', (e) => { e.stopPropagation(); pick(z.id); });
      hotLayer.appendChild(b);
      hot[z.id] = b;
    });
  }
  const v = new THREE.Vector3();
  const box = new THREE.Box3();
  const camDir = new THREE.Vector3();
  function placeHotspots() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    camDir.copy(camera.position).sub(controls.target).normalize();
    for (const id in hot) {
      box.setFromObject(anchors[id]);
      box.getCenter(v);
      const facing = v.clone().sub(new THREE.Vector3(v.x * 0.2, 0.5, 0)).normalize().dot(camDir);
      v.project(camera);
      const x = (v.x * 0.5 + 0.5) * w, y = (-v.y * 0.5 + 0.5) * h;
      const el = hot[id];
      el.style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)';
      const hidden = v.z > 1 || x < 8 || x > w - 8 || y < 8 || y > h - 8 || (!xray && facing < -0.15);
      el.classList.toggle('is-back', hidden);
    }
  }

  /* ------------------------------------------------ raio-x */
  let xray = false;
  const fade = { v: 1 };
  function setXray(on, user) {
    xray = on;
    xrayBtn.setAttribute('aria-pressed', String(on));
    xrayBtn.classList.toggle('is-on', on);
    stage.classList.toggle('is-xray', on);
    const to = on ? 0.1 : 1;
    const apply = () => shellMats.forEach((m) => {
      const t = fade.v < 0.995;
      if (m.transparent !== t) { m.transparent = t; m.needsUpdate = true; }
      m.opacity = fade.v;
      m.depthWrite = !t;
    });
    if (gsap && !reduce) gsap.to(fade, { v: to, duration: 0.6, ease: 'power2.inOut', onUpdate: apply, onComplete: apply });
    else { fade.v = to; apply(); }
    if (user) userXray = on;
    kick();
  }
  let userXray = false;
  xrayBtn.addEventListener('click', () => setXray(!xray, true));

  /* ------------------------------------------------ seleção */
  let active = null;
  let pulse = null;
  let pending = null;
  function highlight(id, strength) {
    (zoneMeshes[id] || []).forEach((m) => {
      if (!m.material.emissive) return;
      m.material.emissive.copy(RED);
      m.material.emissiveIntensity = strength;
    });
  }
  function clearHighlight(id) {
    (zoneMeshes[id] || []).forEach((m) => {
      if (!m.material.emissive) return;
      m.material.emissive.copy(m.userData.base.emissive || new THREE.Color(0));
      m.material.emissiveIntensity = m.userData.base.ei;
    });
  }
  function fly(view) {
    const narrow = camera.aspect < 1.05;
    const pos = new THREE.Vector3().fromArray(view.pos);
    const tgt = new THREE.Vector3().fromArray(view.target);
    if (!view.home) pos.sub(tgt).multiplyScalar(narrow ? 1.65 : 1.4).add(tgt);
    else if (narrow) pos.sub(tgt).multiplyScalar(1.22).add(tgt);
    controls.autoRotate = false;
    if (gsap && !reduce) {
      gsap.to(camera.position, { x: pos.x, y: pos.y, z: pos.z, duration: 1.3, ease: 'power3.inOut', onUpdate: kick });
      gsap.to(controls.target, { x: tgt.x, y: tgt.y, z: tgt.z, duration: 1.3, ease: 'power3.inOut', onUpdate: kick });
    } else { camera.position.copy(pos); controls.target.copy(tgt); kick(); }
  }
  function select(id) {
    if (!car) { pending = id; return; }
    const z = D.zones.find((x) => x.id === id);
    if (!z) return;
    if (active && active !== id) clearHighlight(active);
    if (pulse) { pulse.kill(); pulse = null; }
    active = id;
    for (const k in hot) hot[k].classList.toggle('is-on', k === id);
    if (!userXray) setXray(!!z.xray, false);
    const p = { v: 0.35 };
    if (gsap && !reduce) pulse = gsap.to(p, { v: 1.4, duration: 0.6, ease: 'sine.inOut', yoyo: true, repeat: 5, onUpdate: () => { highlight(id, p.v); kick(); }, onComplete: () => { pulse = null; highlight(id, 0.9); kick(); } });
    else highlight(id, 1);
    fly(z.view);
    if (hint) hint.textContent = z.name + ' em destaque · arraste para ver de outro ângulo';
  }
  function pick(id) {
    select(id);
    window.dispatchEvent(new CustomEvent('cars:picked', { detail: { id } }));
  }
  window.addEventListener('cars:select', (e) => select(e.detail.id));

  /* ------------------------------------------------ toque e hover no carro */
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let down = null;
  function hit(e) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const list = xray ? pickables.filter((o) => !o.userData.shell) : pickables;
    const hits = ray.intersectObjects(list, false);
    if (!hits.length) return null;
    const o = hits[0].object;
    if (o.userData.zone) return o.userData.zone;
    // tocou a lataria: escolhe o sistema mais perto do ponto
    let best = null, bd = 1.1;
    for (const id in anchors) {
      box.setFromObject(anchors[id]);
      box.getCenter(v);
      const d = v.distanceTo(hits[0].point);
      if (d < bd) { bd = d; best = id; }
    }
    return best;
  }
  canvas.addEventListener('pointerdown', (e) => { down = { x: e.clientX, y: e.clientY }; controls.autoRotate = false; });
  canvas.addEventListener('pointerup', (e) => {
    if (!down || !car) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    down = null;
    if (moved > 6) return;
    const id = hit(e);
    if (id) pick(id);
  });
  let hoverId = null;
  let hoverRAF = 0;
  canvas.addEventListener('pointermove', (e) => {
    if (e.pointerType !== 'mouse' || hoverRAF || !car) return;
    hoverRAF = requestAnimationFrame(() => {
      hoverRAF = 0;
      const id = hit(e);
      canvas.style.cursor = id ? 'pointer' : 'grab';
      if (id === hoverId) return;
      if (hoverId && hoverId !== active) clearHighlight(hoverId);
      hoverId = id;
      if (id && id !== active) highlight(id, 0.35);
      for (const k in hot) hot[k].classList.toggle('is-hover', k === id);
      kick();
    });
  });
  canvas.addEventListener('pointerleave', () => {
    if (hoverId && hoverId !== active) clearHighlight(hoverId);
    hoverId = null;
    for (const k in hot) hot[k].classList.remove('is-hover');
  });
  controls.addEventListener('start', () => { if (hint) hint.classList.add('is-gone'); });
  controls.addEventListener('change', kick);

  /* ------------------------------------------------ zoom e vista inicial */
  document.querySelectorAll('[data-zoom]').forEach((b) => b.addEventListener('click', () => {
    const k = b.dataset.zoom === 'in' ? 0.8 : 1.25;
    const off = camera.position.clone().sub(controls.target).multiplyScalar(k);
    const len = THREE.MathUtils.clamp(off.length(), controls.minDistance, controls.maxDistance);
    off.setLength(len);
    const to = controls.target.clone().add(off);
    controls.autoRotate = false;
    if (gsap && !reduce) gsap.to(camera.position, { x: to.x, y: to.y, z: to.z, duration: 0.5, ease: 'power2.out', onUpdate: kick });
    else { camera.position.copy(to); kick(); }
  }));
  document.querySelector('[data-reset]').addEventListener('click', () => {
    fly({ pos: HOME.pos.toArray(), target: HOME.target.toArray(), home: true });
    if (!active && !reduce) setTimeout(() => { controls.autoRotate = true; }, 1400);
  });

  /* ------------------------------------------------ tamanho e loop */
  function resize() {
    const w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (!active) {
      const narrow = camera.aspect < 1.05;
      const pos = HOME.pos.clone().sub(HOME.target).multiplyScalar(narrow ? 1.22 : 1).add(HOME.target);
      if (!started2) camera.position.copy(pos);
    }
    kick();
  }
  let started2 = false;
  new ResizeObserver(resize).observe(stage);

  let visible = true;
  let idle = 0;
  let raf = 0;
  const clock = new THREE.Clock();
  const bornAt = performance.now();
  function kick() { idle = 0; if (!raf && visible && car) raf = requestAnimationFrame(loop); }
  function loop() {
    raf = -1; // ocupado: kick() chamado durante o quadro não agenda outro
    if (controls.autoRotate && performance.now() - bornAt > 25000) controls.autoRotate = false;
    const dt = Math.min(clock.getDelta(), 0.05);
    const spinning = active === 'pneus' || active === 'freios';
    if (spinning && !reduce) spinners.forEach((o) => { o.rotation.z -= dt * 3.2; });
    controls.update();
    renderer.render(scene, camera);
    placeHotspots();
    idle++;
    const busy = controls.autoRotate || spinning || pulse || idle < 90;
    raf = busy && visible ? requestAnimationFrame(loop) : 0;
  }
  function start() {
    started2 = true;
    clock.getDelta();
    kick();
  }
  new IntersectionObserver((es) => {
    visible = es[0].isIntersecting;
    if (visible) kick();
  }).observe(stage);
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; if (visible) kick(); });
}
