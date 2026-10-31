// One bike spot in 3D, seen from where you would stand in front of it: the rack model with
// a blue glowing pad on every free slot and a parked bike on every taken one, in front of
// the real photo of the spot. The camera is fixed; there is nothing to steer.
//
// The app calls BikeSpot.show({id, kind, known, slots}) once and BikeSpot.update(slots, known)
// on every change, with slots as [{id, label, occupied}] from the API. While `known` is false
// (no camera has reported yet) the pads stay grey instead of claiming the spot is empty. Opened in a browser on its
// own (spot.html?id=curved-shelter-a&kind=curved_shelter&slots=10) it runs a demo.

(function () {
  "use strict";

  const BLUE = 0x00aeef; // Brand.blue in the app: free
  const RED = 0xd50c2f; // Brand.red: taken
  const MIST = 0xa4b3bc; // Brand.mist: not known yet
  const STEEL = new THREE.MeshStandardMaterial({ color: 0x6f7980, metalness: 0.7, roughness: 0.35 });
  const DARK_STEEL = new THREE.MeshStandardMaterial({ color: 0x4c555c, metalness: 0.6, roughness: 0.5 });
  const GLASS = new THREE.MeshStandardMaterial({ color: 0xcfe3ee, metalness: 0.1, roughness: 0.15,
    transparent: true, opacity: 0.38, side: THREE.DoubleSide, depthWrite: false });
  const CONCRETE = new THREE.MeshStandardMaterial({ color: 0xc9c7c2, roughness: 0.95 });
  const PAINT = new THREE.MeshBasicMaterial({ color: 0xf2c500 });
  const BIKE_COLOURS = [0x24282c, 0x2f3c4f, 0xb3262e, 0x3f4a3c, 0xd9dcdf, 0x1d1f22, 0x7a2f8c, 0x2a5f8f];

  // Per kind: slot pitch and what to build. Sizes in metres, from the site photos.
  const KINDS = {
    curved_shelter: { pitch: 0.5, build: curvedShelter },
    open_stand: { pitch: 0.6, build: openStand },
    long_shelter: { pitch: 0.6, build: longShelter },
    bike_garage: { pitch: 0.55, build: bikeGarage },
  };

  let renderer, scene, camera, sun;
  let view = { eye: new THREE.Vector3(0, 1.65, 7), target: new THREE.Vector3(0, 0.7, 0), fov: 64 };
  let slots = []; // {pad, beam, bike, occupied, shown}
  let known = true;
  const clock = new THREE.Clock();

  function setup() {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0x000000, 0);
    document.body.appendChild(renderer.domElement);

    camera = new THREE.PerspectiveCamera(50, 1, 0.1, 300);
    window.addEventListener("resize", resize);
    resize();
    renderer.setAnimationLoop(render);
  }

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    // Keep the horizontal field of view fixed so a wide rack fits a narrow portrait phone.
    const half = THREE.MathUtils.degToRad(view.fov / 2);
    camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(half) / camera.aspect));
    camera.fov = Math.min(camera.fov, 100);
    camera.updateProjectionMatrix();
  }

  function show(config) {
    const kind = KINDS[config.kind] ? config.kind : "curved_shelter";
    const photo = document.getElementById("photo");
    const image = new Image();
    image.onload = () => photo.classList.add("ready");
    image.src = "photos/" + config.id + ".jpg";
    photo.style.backgroundImage = "url('" + image.src + "')";

    scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xeaf4ff, 0x7c7a74, 0.75));
    sun = new THREE.DirectionalLight(0xffffff, 2.1);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.radius = 4;
    sun.shadow.bias = -0.0004;
    scene.add(sun, sun.target);

    // Catches the shadows on top of the photo, so the rack stands on the ground.
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.ShadowMaterial({ opacity: 0.3 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const n = config.slots.length;
    const spec = KINDS[kind];
    const places = spec.build(scene, n, spec.pitch);
    slots = places.map((place, i) => makeSlot(place, spec.pitch, i));
    update(config.slots, config.known !== false, true);

    // Sun and shadow camera sized to the model.
    const box = new THREE.Box3().setFromObject(scene.children.find((o) => o.isGroup) || scene);
    const stage = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({
      map: glowTexture(), transparent: true, opacity: 0.85, depthWrite: false }));
    const extent = box.getSize(new THREE.Vector3());
    stage.scale.set(extent.x + 3, extent.z + 3, 1);
    stage.rotation.x = -Math.PI / 2;
    stage.position.set(box.getCenter(new THREE.Vector3()).x, 0.002, box.getCenter(new THREE.Vector3()).z + 0.3);
    stage.renderOrder = -1;
    scene.add(stage);
    const size = box.getSize(new THREE.Vector3()).length();
    sun.position.set(-size * 0.35, size * 0.6, size * 0.45);
    Object.assign(sun.shadow.camera, { left: -size, right: size, top: size, bottom: -size, far: size * 3 });
    sun.shadow.camera.updateProjectionMatrix();
    resize();
  }

  function update(list, isKnown, instant) {
    known = isKnown;
    list.forEach((slot, i) => {
      const s = slots[i];
      if (!s) return;
      s.occupied = slot.occupied;
      if (instant) s.shown = s.occupied ? 1 : 0;
    });
  }

  // A slot: pad on the ground, a light beam while it is free, a bike while it is taken.
  function makeSlot(place, pitch, index) {
    const pad = new THREE.Mesh(roundedRect(pitch * 0.82, 1.5, 0.12),
      new THREE.MeshBasicMaterial({ color: BLUE, transparent: true, opacity: 0.75, depthWrite: false, toneMapped: false }));
    pad.rotation.x = -Math.PI / 2;
    pad.position.set(0, 0.012, 0.35);
    place.add(pad);

    const beam = new THREE.Mesh(new THREE.PlaneGeometry(pitch * 0.7, 1.5),
      new THREE.MeshBasicMaterial({ map: beamTexture(), color: BLUE, transparent: true, opacity: 0.6,
        depthWrite: false, side: THREE.DoubleSide, toneMapped: false }));
    beam.position.set(0, 0.75, 0.35);
    place.add(beam);

    const bike = makeBike(BIKE_COLOURS[(index * 5 + 3) % BIKE_COLOURS.length]);
    bike.position.set(0, 0, 0.2);
    place.add(bike);
    return { pad, beam, bike, occupied: false, shown: 0, phase: index * 0.7 };
  }

  function render() {
    if (!scene) return;
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;

    // Ease in from a little further away, then sway gently as if standing there.
    const intro = 1 - Math.pow(1 - Math.min(t / 1.8, 1), 3);
    camera.position.copy(view.eye).multiplyScalar(1).add(new THREE.Vector3(
      Math.sin(t * 0.23) * 0.35, Math.sin(t * 0.17) * 0.05, (1 - intro) * 2.5));
    camera.lookAt(view.target);

    for (const s of slots) {
      s.shown += ((s.occupied ? 1 : 0) - s.shown) * Math.min(dt * 6, 1);
      const free = 1 - s.shown;
      s.bike.visible = known && s.shown > 0.02;
      s.bike.scale.setScalar(0.6 + 0.4 * s.shown);
      s.bike.position.y = (1 - s.shown) * 0.3;
      s.pad.material.color.setHex(!known ? MIST : s.shown > 0.5 ? RED : BLUE);
      s.pad.material.opacity = s.shown > 0.5 ? 0.85 : 0.6 + 0.3 * (0.5 + 0.5 * Math.sin(t * 2.2 + s.phase));
      s.beam.visible = known && free > 0.02;
      s.beam.material.opacity = free * (0.45 + 0.2 * Math.sin(t * 2.2 + s.phase));
      s.beam.lookAt(camera.position.x, s.beam.getWorldPosition(new THREE.Vector3()).y, camera.position.z);
    }
    renderer.render(scene, camera);
  }

  // ---- Kinds ---------------------------------------------------------------------------

  // Row of `n` slot anchors along x, centred, each facing the camera (+z).
  function row(parent, n, pitch, z = 0, x0 = 0) {
    const places = [];
    for (let i = 0; i < n; i++) {
      const place = new THREE.Group();
      place.position.set(x0 + (i - (n - 1) / 2) * pitch, 0, z);
      parent.add(place);
      places.push(place);
    }
    return places;
  }

  // Standing a few steps in front and to the right, looking along the rack at about 35°,
  // the way the site photos were taken; a long rack then fits a portrait screen.
  function frontCamera(width, targetHeight = 0.85, closeness = 1) {
    const distance = Math.max(3.0, (width * 0.5 + 1.9) * closeness);
    const angle = THREE.MathUtils.degToRad(35);
    view.eye.set(Math.sin(angle) * distance, 1.6 + width * 0.08, Math.cos(angle) * distance);
    view.target.set(width * 0.07, targetHeight, -0.3);
  }

  // The galvanised shelters with a curved polycarbonate roof along the silver facade.
  function curvedShelter(scene, n, pitch) {
    const length = n * pitch + 0.7, depth = 2.0, height = 2.2;
    const group = new THREE.Group();
    scene.add(group);
    const arc = (t) => new THREE.Vector3(0, height * Math.sin(t), depth / 2 - depth * Math.cos(t));
    const profile = [];
    for (let i = 0; i <= 24; i++) profile.push(arc((i / 24) * Math.PI / 2));

    const arches = Math.max(3, Math.round(length / 1.3) + 1);
    for (let i = 0; i < arches; i++) {
      const x = -length / 2 + (length * i) / (arches - 1);
      group.add(tube(profile.map((p) => p.clone().setX(x)), 0.03, STEEL));
    }
    for (const x of [-length / 2, 0, length / 2]) {
      group.add(tube([new THREE.Vector3(x, 0, depth / 2), new THREE.Vector3(x, height, depth / 2)], 0.035, STEEL));
    }
    for (const i of [0, 9, 17, 24]) {
      const p = profile[i];
      group.add(tube([new THREE.Vector3(-length / 2, p.y, p.z), new THREE.Vector3(length / 2, p.y, p.z)], 0.025, STEEL));
    }
    group.add(new THREE.Mesh(sweep(profile, length), GLASS));
    for (const x of [-length / 2, length / 2]) {
      const shape = new THREE.Shape(profile.map((p) => new THREE.Vector2(p.z, p.y)));
      shape.lineTo(depth / 2, 0.08);
      const panel = new THREE.Mesh(new THREE.ShapeGeometry(shape), GLASS);
      panel.rotation.y = -Math.PI / 2;
      panel.position.x = x;
      group.add(panel);
    }
    rack(group, n, pitch, -depth / 2 + 0.3);
    frontCamera(length);
    return row(group, n, pitch, -0.2);
  }

  // Wheel holders on the asphalt, framed by the yellow "VELOS" marking.
  function openStand(scene, n, pitch) {
    const length = n * pitch + 0.8;
    const group = new THREE.Group();
    scene.add(group);
    const w = 0.08;
    for (const [x, z, sx, sz] of [[0, -0.9, length, w], [0, 1.4, length, w], [-length / 2, 0.25, w, 2.3], [length / 2, 0.25, w, 2.3]]) {
      const line = new THREE.Mesh(new THREE.PlaneGeometry(sx, sz), PAINT);
      line.rotation.x = -Math.PI / 2;
      line.position.set(x, 0.006, z);
      group.add(line);
    }
    rack(group, n, pitch, -0.6);
    frontCamera(length, 0.35, 0.78);
    return row(group, n, pitch, -0.3);
  }

  // The long flat steel roof by the bus stop, five slots per bay on concrete feet.
  function longShelter(scene, n, pitch) {
    const bays = Math.ceil(n / 5), bay = 5 * pitch, length = bays * bay, depth = 2.5, height = 2.4;
    const group = new THREE.Group();
    scene.add(group);
    const roof = new THREE.Mesh(new THREE.BoxGeometry(length + 0.4, 0.12, depth + 0.5), DARK_STEEL);
    roof.position.set(0, height, 0);
    roof.castShadow = true;
    group.add(roof);
    for (let i = 0; i <= bays; i++) {
      const x = -length / 2 + i * bay;
      for (const z of [-depth / 2, depth / 2]) {
        group.add(tube([new THREE.Vector3(x, 0.25, z), new THREE.Vector3(x, height, z)], 0.045, STEEL));
        const foot = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.25, 0.35), CONCRETE);
        foot.position.set(x, 0.125, z);
        foot.castShadow = true;
        group.add(foot);
      }
    }
    // Wire mesh on the two ends.
    for (const x of [-length / 2, length / 2]) {
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(depth, height - 0.3),
        new THREE.MeshStandardMaterial({ map: gridTexture(), transparent: true, side: THREE.DoubleSide, depthWrite: false }));
      mesh.rotation.y = Math.PI / 2;
      mesh.position.set(x, 0.3 + (height - 0.3) / 2, 0);
      group.add(mesh);
    }
    rack(group, n, pitch, -depth / 2 + 0.35);
    // Stand in front of one end and look along the roof: the nearest bays are close,
    // the rest of the shelter runs off into the distance.
    view.eye.set(length / 2 - 1.2, 1.75, 4.6);
    view.target.set(length / 2 - 8, 0.9, -0.8);
    view.fov = 70;
    return row(group, n, pitch, -0.2);
  }

  // The underground garage: double-sided floor racks in rows, seen down the aisle.
  function bikeGarage(scene, n, pitch) {
    const rows = 4, perSide = Math.ceil(n / rows / 2), length = perSide * pitch;
    const group = new THREE.Group();
    scene.add(group);
    const places = [];
    for (let r = 0; r < rows; r++) {
      const z = -r * 3.2;
      const rail = tube([new THREE.Vector3(-length / 2, 0.08, z), new THREE.Vector3(length / 2, 0.08, z)], 0.025, STEEL);
      group.add(rail);
      for (const side of [1, -1]) {
        const holder = new THREE.Group();
        holder.position.z = z;
        holder.rotation.y = side === 1 ? 0 : Math.PI;
        group.add(holder);
        rack(holder, perSide, pitch, -0.05);
        places.push(...row(holder, perSide, pitch, 0.3));
      }
    }
    // Standing in the aisle at the front of the rows.
    view.eye.set(length * 0.55, 1.75, 2.6);
    view.target.set(-0.3, 0.35, -4.5);
    view.fov = 72;
    return places.slice(0, n);
  }

  // Front-wheel holders: a vertical loop per slot on a rail along x.
  function rack(parent, n, pitch, z) {
    const rail = tube([new THREE.Vector3(-(n * pitch) / 2, 0.06, z), new THREE.Vector3((n * pitch) / 2, 0.06, z)], 0.02, STEEL);
    parent.add(rail);
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * pitch;
      const loop = [];
      for (let k = 0; k <= 12; k++) {
        const a = Math.PI * (k / 12);
        loop.push(new THREE.Vector3(x, 0.06 + Math.sin(a) * 0.38, z + 0.18 - Math.cos(a) * 0.18 - 0.18));
      }
      parent.add(tube(loop, 0.012, STEEL));
    }
  }

  // ---- Parts ---------------------------------------------------------------------------

  function makeBike(colour) {
    const bike = new THREE.Group();
    const frame = new THREE.MeshStandardMaterial({ color: colour, metalness: 0.35, roughness: 0.45 });
    const tyre = new THREE.MeshStandardMaterial({ color: 0x18191b, roughness: 0.9 });
    const wheel = new THREE.TorusGeometry(0.33, 0.026, 8, 32);
    for (const z of [-0.52, 0.52]) {
      const w = new THREE.Mesh(wheel, tyre);
      w.rotation.y = Math.PI / 2;
      w.position.set(0, 0.35, z);
      w.castShadow = true;
      bike.add(w);
    }
    const p = (z, y) => new THREE.Vector3(0, y, z);
    const front = p(-0.52, 0.35), rear = p(0.52, 0.35), crank = p(0.02, 0.3);
    const seat = p(0.22, 0.86), headTop = p(-0.36, 0.9), headLow = p(-0.39, 0.74);
    for (const [a, b] of [[crank, seat], [crank, headLow], [seat, headTop], [crank, rear], [seat, rear], [headLow, front], [headTop, p(-0.34, 1.02)]]) {
      bike.add(rod(a, b, 0.018, frame));
    }
    const bar = rod(new THREE.Vector3(-0.27, 1.02, -0.34), new THREE.Vector3(0.27, 1.02, -0.34), 0.014, tyre);
    const saddle = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.05, 0.26), tyre);
    saddle.position.set(0, 0.92, 0.25);
    bike.add(bar, saddle);
    bike.traverse((o) => { if (o.isMesh) o.castShadow = true; });
    return bike;
  }

  function tube(points, radius, material) {
    const path = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0);
    const mesh = new THREE.Mesh(new THREE.TubeGeometry(path, Math.max(points.length * 3, 8), radius, 8), material);
    mesh.castShadow = true;
    return mesh;
  }

  function rod(a, b, radius, material) {
    const length = a.distanceTo(b);
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, 8), material);
    mesh.position.copy(a).add(b).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    return mesh;
  }

  // A surface following `profile` (points in y/z) across the full length along x.
  function sweep(profile, length) {
    const positions = [], index = [];
    profile.forEach((p) => {
      positions.push(-length / 2, p.y, p.z, length / 2, p.y, p.z);
    });
    for (let i = 0; i < profile.length - 1; i++) {
      const a = i * 2;
      index.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(index);
    geometry.computeVertexNormals();
    return geometry;
  }

  function roundedRect(w, h, r) {
    const s = new THREE.Shape();
    s.moveTo(-w / 2 + r, -h / 2);
    s.lineTo(w / 2 - r, -h / 2); s.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
    s.lineTo(w / 2, h / 2 - r); s.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
    s.lineTo(-w / 2 + r, h / 2); s.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
    s.lineTo(-w / 2, -h / 2 + r); s.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
    return new THREE.ShapeGeometry(s);
  }

  let beamCache;
  function beamTexture() {
    if (beamCache) return beamCache;
    const canvas = document.createElement("canvas");
    canvas.width = 32; canvas.height = 128;
    const g = canvas.getContext("2d");
    const vertical = g.createLinearGradient(0, 128, 0, 0);
    vertical.addColorStop(0, "rgba(255,255,255,0.9)");
    vertical.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = vertical;
    g.fillRect(0, 0, 32, 128);
    // Soft sides.
    g.globalCompositeOperation = "destination-in";
    const sides = g.createLinearGradient(0, 0, 32, 0);
    sides.addColorStop(0, "rgba(0,0,0,0)"); sides.addColorStop(0.5, "rgba(0,0,0,1)"); sides.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = sides;
    g.fillRect(0, 0, 32, 128);
    beamCache = new THREE.CanvasTexture(canvas);
    return beamCache;
  }

  // A soft light ellipse the rack stands on, so it sits on the photo instead of floating.
  function glowTexture() {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const g = canvas.getContext("2d");
    const gradient = g.createRadialGradient(128, 128, 10, 128, 128, 128);
    gradient.addColorStop(0, "rgba(250,252,253,0.95)");
    gradient.addColorStop(0.6, "rgba(242,246,248,0.7)");
    gradient.addColorStop(1, "rgba(242,246,248,0)");
    g.fillStyle = gradient;
    g.fillRect(0, 0, 256, 256);
    return new THREE.CanvasTexture(canvas);
  }

  function gridTexture() {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const g = canvas.getContext("2d");
    g.strokeStyle = "rgba(90,100,108,0.85)";
    g.lineWidth = 2;
    for (let i = 0; i <= 256; i += 16) {
      g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 256); g.stroke();
      g.beginPath(); g.moveTo(0, i); g.lineTo(256, i); g.stroke();
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(3, 3);
    return texture;
  }

  setup();
  window.BikeSpot = { show, update: (list, isKnown) => update(list, isKnown !== false, false) };

  // Standalone preview with made-up occupancy that keeps changing.
  const params = new URLSearchParams(location.search);
  if (params.has("kind")) {
    const count = Number(params.get("slots") || 10);
    const demo = Array.from({ length: count }, (_, i) => ({ id: String(i + 1), label: i + 1, occupied: Math.random() < 0.55 }));
    show({ id: params.get("id") || "curved-shelter-a", kind: params.get("kind"), slots: demo });
    setInterval(() => {
      const slot = demo[Math.floor(Math.random() * demo.length)];
      slot.occupied = !slot.occupied;
      update(demo, true, false);
    }, 2500);
  }
})();
