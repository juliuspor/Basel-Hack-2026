// One bike spot in a 3D model of the Endress+Hauser block. The view starts high above the
// block and flies down, like Google Earth, until you stand right in front of the rack: a
// blue glowing pad on every free slot and a parked bike on every taken one. Once landed, a
// sideways drag slides you along the rack, to look for landmarks; you cannot walk away.
//
// The world comes from site.js (OpenStreetMap buildings, streets, car parks and trees,
// written by code/scene-generator/site_world.py). The app calls
// BikeSpot.show({id, kind, center, polygon, known, slots}) once and
// BikeSpot.update(slots, known) on every change, with slots as [{id, label, occupied}] and
// center/polygon as [lat, lon] from the API. While `known` is false (no camera has reported
// yet) the pads stay grey instead of claiming the spot is empty. Opened in a browser on its
// own (spot.html?kind=curved_shelter&slots=10&lat=47.48683&lon=7.59919) it runs a demo.

(function () {
  "use strict";

  // Treat colours as sRGB like the rest of the page; r149 defaults to linear, which washes
  // every material out. Must run before the first material is made.
  THREE.ColorManagement.legacyMode = false;

  const BLUE = 0x00aeef; // Brand.blue in the app: free
  const RED = 0xd50c2f; // Brand.red: taken
  const MIST = 0xa4b3bc; // Brand.mist: not known yet
  const HORIZON = 0xe2ebf1; // fog colour, matches the bottom of the CSS sky
  const FLIGHT_SECONDS = 3.6;
  const EYE_HEIGHT = 1.7;

  const STEEL = new THREE.MeshStandardMaterial({ color: 0x6f7980, metalness: 0.7, roughness: 0.35 });
  const DARK_STEEL = new THREE.MeshStandardMaterial({ color: 0x4c555c, metalness: 0.6, roughness: 0.5 });
  const GLASS = new THREE.MeshStandardMaterial({ color: 0xcfe3ee, metalness: 0.1, roughness: 0.15,
    transparent: true, opacity: 0.38, side: THREE.DoubleSide, depthWrite: false });
  const CONCRETE = new THREE.MeshStandardMaterial({ color: 0xc9c7c2, roughness: 0.95 });
  const BIKE_COLOURS = [0x24282c, 0x2f3c4f, 0xb3262e, 0x3f4a3c, 0xd9dcdf, 0x1d1f22, 0x7a2f8c, 0x2a5f8f];

  // Per kind of rack: slot pitch, how to build it, and how much of it to keep in view.
  const KINDS = {
    curved_shelter: { pitch: 0.5, build: curvedShelter },
    open_stand: { pitch: 0.6, build: openStand },
    long_shelter: { pitch: 0.6, build: longShelter, view: 10 },
    bike_garage: { pitch: 0.55, build: bikeGarage },
  };

  let renderer, scene, camera, sun, clouds = [];
  let flight = null; // {start, eye: [P0..P3], target: [from, to], right, limit, perPixel}
  const pan = { offset: 0, goal: 0, speed: 0, lastX: null, lastTime: 0 }; // metres along the rack
  let slots = []; // {pad, beam, bike, occupied, shown}
  let known = true;
  const FOV = 72; // vertical, close to a phone camera held upright
  const MAX_DISTANCE = 18; // far enough back to see a whole rack on a narrow screen
  const clock = new THREE.Clock();

  // ---- World ---------------------------------------------------------------------------

  function setup() {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0x000000, 0);
    document.body.appendChild(renderer.domElement);

    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(HORIZON, 420, 1600);
    scene.add(new THREE.HemisphereLight(0xe3f0ff, 0x8f8e86, 0.8));
    sun = new THREE.DirectionalLight(0xfff6e8, 2.0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.0005;
    sun.shadow.radius = 3;
    Object.assign(sun.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45, near: 1, far: 400 });
    scene.add(sun, sun.target);
    aimSun(new THREE.Vector3());

    camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 3000);
    buildWorld(window.SITE);
    camera.position.set(0, 330, 260);
    camera.lookAt(0, 0, 0);
    window.addEventListener("resize", resize);
    resize();
    renderer.setAnimationLoop(render);
  }

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  // Sun low in the south-west, its shadow box following the spot.
  function aimSun(at) {
    sun.target.position.copy(at);
    sun.position.copy(at).add(new THREE.Vector3(-90, 150, 110));
    sun.shadow.camera.updateProjectionMatrix();
  }

  // Local metres (x east, y north) to the scene (x east, z south).
  const toScene = (p, y = 0) => new THREE.Vector3(p[0], y, -p[1]);

  function buildWorld(site) {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(3000, 3000),
      new THREE.MeshStandardMaterial({ color: 0xc4c9c0, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const asphalt = new THREE.MeshStandardMaterial({ color: 0x585e64, roughness: 0.95 });
    const lot = new THREE.MeshStandardMaterial({ color: 0x8d9296, roughness: 0.95 });
    const path = new THREE.MeshStandardMaterial({ color: 0xc9c4b8, roughness: 1 });
    const paint = new THREE.MeshBasicMaterial({ color: 0xf4f4f0 });

    for (const ring of site.parking) {
      const mesh = new THREE.Mesh(flat(ring), lot);
      mesh.position.y = 0.02;
      mesh.receiveShadow = true;
      scene.add(mesh);
    }
    for (const road of site.roads) {
      const isPath = road.kind === "path";
      const mesh = new THREE.Mesh(ribbon(road.line, road.width), isPath ? path : asphalt);
      mesh.position.y = isPath ? 0.025 : 0.03;
      mesh.receiveShadow = true;
      scene.add(mesh);
      if (!isPath && road.width >= 6) {
        const dashes = new THREE.Mesh(dashLine(road.line), paint);
        dashes.position.y = 0.04;
        scene.add(dashes);
      }
    }

    const looks = {
      endress: [new THREE.MeshStandardMaterial({ map: solarTexture(), roughness: 0.6, metalness: 0.2 }),
        new THREE.MeshStandardMaterial({ map: facadeTexture("#cfd5da", "#3b4b59", 0.42), roughness: 0.55, metalness: 0.25 })],
      office: [new THREE.MeshStandardMaterial({ color: 0xa9aba7, roughness: 0.95 }),
        new THREE.MeshStandardMaterial({ map: facadeTexture("#efede7", "#55646f", 0.36), roughness: 0.85 })],
    };
    for (const building of site.buildings) {
      const shape = new THREE.Shape(building.outline.map((p) => new THREE.Vector2(p[0], p[1])));
      const geometry = new THREE.ExtrudeGeometry(shape, { depth: building.height, bevelEnabled: false });
      geometry.rotateX(-Math.PI / 2);
      const mesh = new THREE.Mesh(geometry, looks[building.style] || looks.office);
      mesh.castShadow = mesh.receiveShadow = true;
      scene.add(mesh);
    }

    // Trees as two instanced meshes, so 180 of them stay cheap.
    const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.16, 0.24, 3, 6),
      new THREE.MeshStandardMaterial({ color: 0x6b5442, roughness: 1 }), site.trees.length);
    const crowns = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(2.3, 1),
      new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9, flatShading: true }), site.trees.length);
    const m = new THREE.Matrix4(), colour = new THREE.Color();
    site.trees.forEach((p, i) => {
      const s = 0.8 + ((i * 37) % 10) / 20;
      m.makeScale(s, s, s).setPosition(p[0], 1.5 * s, -p[1]);
      trunks.setMatrixAt(i, m);
      m.makeScale(s, s * 1.15, s).setPosition(p[0], 4.3 * s, -p[1]);
      crowns.setMatrixAt(i, m);
      crowns.setColorAt(i, colour.setHSL(0.27 + ((i * 13) % 7) / 100, 0.42, 0.36 + ((i * 7) % 5) / 60));
    });
    trunks.castShadow = crowns.castShadow = true;
    scene.add(trunks, crowns);

    const puff = cloudTexture();
    for (let i = 0; i < 9; i++) {
      const cloud = new THREE.Sprite(new THREE.SpriteMaterial({ map: puff, transparent: true, opacity: 0.85,
        depthWrite: false, fog: false }));
      cloud.scale.set(120 + (i % 3) * 40, 50 + (i % 2) * 20, 1);
      cloud.position.set(-400 + i * 100, 170 + (i % 4) * 22, -350 + ((i * 173) % 700));
      scene.add(cloud);
      clouds.push(cloud);
    }
  }

  // ---- The spot ------------------------------------------------------------------------

  function show(config) {
    const kind = KINDS[config.kind] ? config.kind : "curved_shelter";
    const spec = KINDS[kind];
    const site = window.SITE;
    const local = (ll) => [(ll[1] - site.origin[1]) * 111320 * Math.cos(site.origin[0] * Math.PI / 180),
      (ll[0] - site.origin[0]) * 111320];
    const centre = local(config.center);
    // The outline's first edge runs along the rack (backend `footprint`).
    let heading = 0;
    if (config.polygon && config.polygon.length > 1) {
      const a = local(config.polygon[0]), b = local(config.polygon[1]);
      heading = Math.atan2(b[1] - a[1], b[0] - a[0]);
    }

    const holder = new THREE.Group();
    holder.position.copy(toScene(centre));
    holder.rotation.y = heading;
    scene.add(holder);
    holder.updateMatrixWorld(true); // localToWorld below needs it before the first frame

    const built = spec.build(holder, config.slots.length, spec.pitch);
    slots = built.places.map((place, i) => makeSlot(place, spec.pitch, i));
    update(config.slots, config.known !== false, true);
    holder.traverse((o) => { if (o.isMesh) o.castShadow = true; });

    // Land straight in front of the rack, at eye height, far enough back to see it whole
    // on this screen. Looking a little below the rack keeps it above the app's card.
    const across = 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * camera.aspect);
    const visible = Math.min(built.width, spec.view || Infinity);
    let distance = Math.min((visible / 2 + 0.8) / Math.tan(across / 2), MAX_DISTANCE);
    // Step closer if that spot would be inside a building.
    const eyeAt = (d) => holder.localToWorld(new THREE.Vector3(0, EYE_HEIGHT, d));
    while (distance > 3 && site.buildings.some((b) => inside([eyeAt(distance).x, -eyeAt(distance).z], b.outline))) {
      distance -= 0.5;
    }
    const eye = eyeAt(distance);
    const target = holder.localToWorld(new THREE.Vector3(0, built.lookHeight ?? 0.35, -0.4));
    const front = holder.localToWorld(new THREE.Vector3(0, 0, 1)).sub(holder.position).normalize();
    aimSun(holder.position);

    const start = camera.position.clone();
    flight = {
      start: clock.elapsedTime,
      eye: [start, holder.position.clone().addScaledVector(front, 110).setY(170),
        holder.position.clone().addScaledVector(front, distance + 22).setY(16), eye],
      target: [new THREE.Vector3(0, 0, 0), target],
      // Sliding runs along the rack, at most to its ends (or 3 m for short ones).
      right: holder.localToWorld(new THREE.Vector3(1, 0, 0)).sub(holder.position).normalize(),
      limit: Math.max(built.width / 2, 3),
      perPixel: (2 * distance * Math.tan(across / 2)) / window.innerWidth,
    };
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
    pad.position.set(0, 0.075, 0.35);
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
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime;

    let arrived = 0;
    if (flight) {
      const k = Math.min((t - flight.start) / FLIGHT_SECONDS, 1);
      const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; // ease in and out
      camera.position.copy(bezier(flight.eye, e));
      const look = flight.target[0].clone().lerp(flight.target[1], Math.min(1, e * 1.25));
      if (k === 1) {
        // Landed: follow the finger along the rack, coasting a little after release.
        if (pan.lastX === null && pan.speed) {
          pan.goal += pan.speed * dt;
          pan.speed *= Math.pow(0.04, dt);
          if (Math.abs(pan.speed) < 0.05) pan.speed = 0;
        }
        pan.goal = THREE.MathUtils.clamp(pan.goal, -flight.limit, flight.limit);
        pan.offset += (pan.goal - pan.offset) * Math.min(dt * 12, 1);
        camera.position.addScaledVector(flight.right, pan.offset);
        look.addScaledVector(flight.right, pan.offset);
        camera.position.y += Math.sin(t * 0.8) * 0.015; // breathe, as if standing there
        if (!landed) {
          landed = true;
          document.body.classList.add("landed");
        }
      }
      camera.lookAt(look);
      arrived = THREE.MathUtils.clamp((k - 0.75) / 0.25, 0, 1);
    }

    for (const cloud of clouds) {
      cloud.position.x += dt * 2.2;
      if (cloud.position.x > 520) cloud.position.x = -520;
    }

    for (const s of slots) {
      s.shown += ((s.occupied ? 1 : 0) - s.shown) * Math.min(dt * 6, 1);
      const free = 1 - s.shown;
      s.bike.visible = known && s.shown > 0.02;
      s.bike.scale.setScalar(0.6 + 0.4 * s.shown);
      s.bike.position.y = (1 - s.shown) * 0.3;
      s.pad.material.color.setHex(!known ? MIST : s.shown > 0.5 ? RED : BLUE);
      const pulse = 0.5 + 0.5 * Math.sin(t * 2.2 + s.phase);
      s.pad.material.opacity = (s.shown > 0.5 ? 0.85 : 0.6 + 0.3 * pulse) * (0.35 + 0.65 * arrived);
      s.beam.visible = known && free > 0.02 && arrived > 0;
      s.beam.material.opacity = free * arrived * (0.45 + 0.2 * Math.sin(t * 2.2 + s.phase));
      const p = s.beam.getWorldPosition(new THREE.Vector3());
      s.beam.lookAt(camera.position.x, p.y, camera.position.z);
    }
    renderer.render(scene, camera);
  }

  // A horizontal drag moves the world with the finger, so you step the other way.
  let landed = false;
  window.addEventListener("pointerdown", (e) => {
    if (!landed) return;
    pan.lastX = e.clientX;
    pan.lastTime = performance.now();
    pan.speed = 0;
  });
  window.addEventListener("pointermove", (e) => {
    if (pan.lastX === null) return;
    const now = performance.now(), step = -(e.clientX - pan.lastX) * flight.perPixel;
    pan.goal += step;
    pan.speed = step / Math.max((now - pan.lastTime) / 1000, 0.008);
    pan.lastX = e.clientX;
    pan.lastTime = now;
  });
  const release = () => { pan.lastX = null; };
  window.addEventListener("pointerup", release);
  window.addEventListener("pointercancel", release);

  function inside([x, y], ring) {
    let hit = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < xi + ((y - yi) * (xj - xi)) / (yj - yi)) hit = !hit;
    }
    return hit;
  }

  function bezier([a, b, c, d], t) {
    const u = 1 - t;
    return a.clone().multiplyScalar(u * u * u).addScaledVector(b, 3 * u * u * t)
      .addScaledVector(c, 3 * u * t * t).addScaledVector(d, t * t * t);
  }

  // ---- Kinds: each builds into `parent` with the open front towards +z -------------------

  // Row of `n` slot anchors along x, centred.
  function row(parent, n, pitch, z = 0) {
    const places = [];
    for (let i = 0; i < n; i++) {
      const place = new THREE.Group();
      place.position.set((i - (n - 1) / 2) * pitch, 0, z);
      parent.add(place);
      places.push(place);
    }
    return places;
  }

  // Paving under a rack, so it reads as its own place on the pavement.
  function paving(parent, width, depth, z) {
    const pad = new THREE.Mesh(new THREE.PlaneGeometry(width, depth),
      new THREE.MeshStandardMaterial({ map: tileTexture(width, depth), roughness: 0.9 }));
    pad.rotation.x = -Math.PI / 2;
    pad.position.set(0, 0.05, z);
    pad.receiveShadow = true;
    parent.add(pad);
  }

  // The galvanised shelters with a curved polycarbonate roof along the silver facade.
  function curvedShelter(parent, n, pitch) {
    const length = n * pitch + 0.7, depth = 2.0, height = 2.2;
    paving(parent, length + 2.4, depth + 4, 0.8);
    const arc = (t) => new THREE.Vector3(0, height * Math.sin(t), depth / 2 - depth * Math.cos(t));
    const profile = [];
    for (let i = 0; i <= 24; i++) profile.push(arc((i / 24) * Math.PI / 2));
    const arches = Math.max(3, Math.round(length / 1.3) + 1);
    for (let i = 0; i < arches; i++) {
      const x = -length / 2 + (length * i) / (arches - 1);
      parent.add(tube(profile.map((p) => p.clone().setX(x)), 0.03, STEEL));
    }
    for (const x of [-length / 2, 0, length / 2]) {
      parent.add(tube([new THREE.Vector3(x, 0, depth / 2), new THREE.Vector3(x, height, depth / 2)], 0.035, STEEL));
    }
    for (const i of [0, 9, 17, 24]) {
      const p = profile[i];
      parent.add(tube([new THREE.Vector3(-length / 2, p.y, p.z), new THREE.Vector3(length / 2, p.y, p.z)], 0.025, STEEL));
    }
    parent.add(new THREE.Mesh(sweep(profile, length), GLASS));
    for (const x of [-length / 2, length / 2]) {
      const shape = new THREE.Shape(profile.map((p) => new THREE.Vector2(p.z, p.y)));
      shape.lineTo(depth / 2, 0.08);
      const panel = new THREE.Mesh(new THREE.ShapeGeometry(shape), GLASS);
      panel.rotation.y = -Math.PI / 2;
      panel.position.x = x;
      parent.add(panel);
    }
    rack(parent, n, pitch, -depth / 2 + 0.3);
    return { places: row(parent, n, pitch, -0.2), width: length };
  }

  // Wheel holders on the asphalt, framed by a yellow marking.
  function openStand(parent, n, pitch) {
    const length = n * pitch + 0.8;
    const yellow = new THREE.MeshBasicMaterial({ color: 0xf2c500 });
    for (const [x, z, sx, sz] of [[0, -0.9, length, 0.08], [0, 1.4, length, 0.08], [-length / 2, 0.25, 0.08, 2.3], [length / 2, 0.25, 0.08, 2.3]]) {
      const line = new THREE.Mesh(new THREE.PlaneGeometry(sx, sz), yellow);
      line.rotation.x = -Math.PI / 2;
      line.position.set(x, 0.055, z);
      parent.add(line);
    }
    rack(parent, n, pitch, -0.6);
    return { places: row(parent, n, pitch, -0.3), width: length, lookHeight: 0.1 };
  }

  // The long flat steel roof by the bus stop, five slots per bay on concrete feet.
  function longShelter(parent, n, pitch) {
    const bays = Math.ceil(n / 5), bay = 5 * pitch, length = bays * bay, depth = 2.5, height = 2.4;
    paving(parent, length + 2, depth + 3.5, 0.6);
    const roof = new THREE.Mesh(new THREE.BoxGeometry(length + 0.4, 0.12, depth + 0.5), DARK_STEEL);
    roof.position.set(0, height, 0);
    parent.add(roof);
    for (let i = 0; i <= bays; i++) {
      const x = -length / 2 + i * bay;
      for (const z of [-depth / 2, depth / 2]) {
        parent.add(tube([new THREE.Vector3(x, 0.25, z), new THREE.Vector3(x, height, z)], 0.045, STEEL));
        const foot = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.25, 0.35), CONCRETE);
        foot.position.set(x, 0.125, z);
        parent.add(foot);
      }
    }
    for (const x of [-length / 2, length / 2]) {
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(depth, height - 0.3),
        new THREE.MeshStandardMaterial({ map: gridTexture(), transparent: true, side: THREE.DoubleSide, depthWrite: false }));
      mesh.rotation.y = Math.PI / 2;
      mesh.position.set(x, 0.3 + (height - 0.3) / 2, 0);
      parent.add(mesh);
    }
    rack(parent, n, pitch, -depth / 2 + 0.35);
    return { places: row(parent, n, pitch, -0.2), width: length };
  }

  // The bike garage: a concrete hall against the facade, open to the street, with rows of
  // double-sided floor racks.
  function bikeGarage(parent, n, pitch) {
    const rows = 2, perSide = Math.ceil(n / rows / 2), width = perSide * pitch + 2.4, depth = 6.4, height = 3.2;
    const walls = new THREE.MeshStandardMaterial({ color: 0xd3d1cc, roughness: 0.95, side: THREE.DoubleSide });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), new THREE.MeshStandardMaterial({ color: 0xe4e6e6, roughness: 0.8 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, 0.04, -depth / 2);
    floor.receiveShadow = true;
    parent.add(floor);
    for (const [w, h, x, y, z, ry] of [[width, height, 0, height / 2, -depth, 0], [depth, height, -width / 2, height / 2, -depth / 2, Math.PI / 2],
      [depth, height, width / 2, height / 2, -depth / 2, Math.PI / 2], [width, depth, 0, height, -depth / 2, 0]]) {
      const panel = new THREE.Mesh(new THREE.PlaneGeometry(w, h), walls);
      panel.position.set(x, y, z);
      if (w === width && h === depth) panel.rotation.x = Math.PI / 2; else panel.rotation.y = ry;
      panel.receiveShadow = true;
      parent.add(panel);
    }
    const strip = new THREE.MeshBasicMaterial({ color: 0xfdfdf6 });
    for (let i = 0; i < 3; i++) {
      const light = new THREE.Mesh(new THREE.PlaneGeometry(0.25, depth - 1), strip);
      light.rotation.x = Math.PI / 2;
      light.position.set(-width / 3 + i * width / 3, height - 0.02, -depth / 2);
      parent.add(light);
    }
    const lamp = new THREE.PointLight(0xffffff, 0.8, 18);
    lamp.position.set(0, height - 0.4, -depth / 2);
    parent.add(lamp);
    const places = [];
    for (let r = 0; r < rows; r++) {
      const holder = new THREE.Group();
      holder.position.z = -1.7 - r * 2.9;
      parent.add(holder);
      for (const side of [1, -1]) {
        const half = new THREE.Group();
        half.rotation.y = side === 1 ? 0 : Math.PI;
        holder.add(half);
        rack(half, perSide, pitch, -0.05);
        places.push(...row(half, perSide, pitch, 0.3));
      }
    }
    return { places: places.slice(0, n), width, lookHeight: 0.9 };
  }

  // Front-wheel holders: a vertical loop per slot on a rail along x.
  function rack(parent, n, pitch, z) {
    parent.add(tube([new THREE.Vector3(-(n * pitch) / 2, 0.06, z), new THREE.Vector3((n * pitch) / 2, 0.06, z)], 0.02, STEEL));
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * pitch;
      const loop = [];
      for (let k = 0; k <= 12; k++) {
        const a = Math.PI * (k / 12);
        loop.push(new THREE.Vector3(x, 0.06 + Math.sin(a) * 0.38, z - Math.cos(a) * 0.18));
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
    return bike;
  }

  function tube(points, radius, material) {
    const path = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0);
    return new THREE.Mesh(new THREE.TubeGeometry(path, Math.max(points.length * 3, 8), radius, 8), material);
  }

  function rod(a, b, radius, material) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, a.distanceTo(b), 8), material);
    mesh.position.copy(a).add(b).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    return mesh;
  }

  // A surface following `profile` (points in y/z) across the full length along x.
  function sweep(profile, length) {
    const positions = [], index = [];
    profile.forEach((p) => positions.push(-length / 2, p.y, p.z, length / 2, p.y, p.z));
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

  // A flat polygon (local metres) lying on the ground.
  function flat(ring) {
    const geometry = new THREE.ShapeGeometry(new THREE.Shape(ring.map((p) => new THREE.Vector2(p[0], p[1]))));
    geometry.rotateX(-Math.PI / 2);
    return geometry;
  }

  // A street `width` wide along `line`: a quad per segment plus a disc at every bend.
  function ribbon(line, width) {
    const parts = [];
    line.forEach((p, i) => {
      if (i > 0) {
        const a = line[i - 1], dx = p[0] - a[0], dy = p[1] - a[1], l = Math.hypot(dx, dy) || 1;
        const nx = (-dy / l) * width / 2, ny = (dx / l) * width / 2;
        parts.push(flat([[a[0] + nx, a[1] + ny], [p[0] + nx, p[1] + ny], [p[0] - nx, p[1] - ny], [a[0] - nx, a[1] - ny]]));
      }
      if (i > 0 && i < line.length - 1) {
        const disc = new THREE.CircleGeometry(width / 2, 16);
        disc.rotateX(-Math.PI / 2);
        disc.translate(p[0], 0, -p[1]);
        parts.push(disc);
      }
    });
    return merge(parts);
  }

  // Centre-line dashes: 3 m painted, 4 m gap.
  function dashLine(line) {
    const parts = [];
    for (let i = 1; i < line.length; i++) {
      const a = line[i - 1], b = line[i], l = Math.hypot(b[0] - a[0], b[1] - a[1]);
      for (let s = 1; s + 3 < l; s += 7) {
        const p = (d) => [a[0] + (b[0] - a[0]) * d / l, a[1] + (b[1] - a[1]) * d / l];
        parts.push(ribbon([p(s), p(s + 3)], 0.15));
      }
    }
    return merge(parts);
  }

  // Joins plain triangle geometries into one, so a street is a single draw call.
  function merge(parts) {
    const positions = [];
    for (const part of parts) {
      const g = part.index ? part.toNonIndexed() : part;
      positions.push(...g.attributes.position.array);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
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

  // ---- Textures, drawn on canvases so the page needs no image files --------------------

  function canvasTexture(size, draw, repeat) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    draw(canvas.getContext("2d"), size);
    const texture = new THREE.CanvasTexture(canvas);
    texture.encoding = THREE.sRGBEncoding;
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    if (repeat) texture.repeat.set(repeat[0], repeat[1]);
    texture.anisotropy = 4;
    return texture;
  }

  // One floor (3.6 m) of facade: wall panels with a band of windows. Extruded walls get
  // UVs in metres, so the texture repeats every 3.6 m.
  function facadeTexture(wall, glass, share) {
    return canvasTexture(256, (g, s) => {
      g.fillStyle = wall; g.fillRect(0, 0, s, s);
      const top = s * (0.62 - share / 2), height = s * share;
      const shine = g.createLinearGradient(0, top, 0, top + height);
      shine.addColorStop(0, glass); shine.addColorStop(1, "#6f8191");
      g.fillStyle = shine; g.fillRect(0, top, s, height);
      g.fillStyle = "rgba(255,255,255,0.35)";
      for (let x = 0; x < s; x += 32) g.fillRect(x, top, 3, height);
      g.fillStyle = "rgba(0,0,0,0.08)";
      g.fillRect(0, s - 4, s, 4);
    }, [1 / 3.6, 1 / 3.6]);
  }

  // Solar panels in rows, like the roofs on the aerial photo of the block.
  function solarTexture() {
    return canvasTexture(256, (g, s) => {
      g.fillStyle = "#c3c6c4"; g.fillRect(0, 0, s, s);
      g.fillStyle = "#2c3d5c";
      for (let y = 8; y < s; y += 64) for (let x = 6; x < s; x += 32) g.fillRect(x, y, 28, 52);
      g.fillStyle = "rgba(255,255,255,0.08)";
      for (let y = 8; y < s; y += 64) g.fillRect(0, y, s, 6);
    }, [1 / 8, 1 / 8]);
  }

  function tileTexture(width, depth) {
    return canvasTexture(128, (g, s) => {
      g.fillStyle = "#c8c7c2"; g.fillRect(0, 0, s, s);
      g.strokeStyle = "#a9a8a3"; g.lineWidth = 2;
      for (let i = 0; i <= s; i += 16) {
        g.beginPath(); g.moveTo(i, 0); g.lineTo(i, s); g.stroke();
        g.beginPath(); g.moveTo(0, i); g.lineTo(s, i); g.stroke();
      }
    }, [width / 2.4, depth / 2.4]);
  }

  let beamCache;
  function beamTexture() {
    return beamCache || (beamCache = canvasTexture(128, (g, s) => {
      const up = g.createLinearGradient(0, s, 0, 0);
      up.addColorStop(0, "rgba(255,255,255,0.9)"); up.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = up; g.fillRect(0, 0, s, s);
      g.globalCompositeOperation = "destination-in";
      const sides = g.createLinearGradient(0, 0, s, 0);
      sides.addColorStop(0, "rgba(0,0,0,0)"); sides.addColorStop(0.5, "rgba(0,0,0,1)"); sides.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = sides; g.fillRect(0, 0, s, s);
    }));
  }

  function gridTexture() {
    return canvasTexture(256, (g, s) => {
      g.strokeStyle = "rgba(90,100,108,0.85)"; g.lineWidth = 2;
      for (let i = 0; i <= s; i += 16) {
        g.beginPath(); g.moveTo(i, 0); g.lineTo(i, s); g.stroke();
        g.beginPath(); g.moveTo(0, i); g.lineTo(s, i); g.stroke();
      }
    }, [3, 3]);
  }

  function cloudTexture() {
    return canvasTexture(128, (g, s) => {
      for (const [x, y, r] of [[0.35, 0.55, 0.3], [0.55, 0.45, 0.32], [0.7, 0.58, 0.25], [0.45, 0.62, 0.28]]) {
        const puff = g.createRadialGradient(x * s, y * s, 0, x * s, y * s, r * s);
        puff.addColorStop(0, "rgba(255,255,255,0.9)"); puff.addColorStop(1, "rgba(255,255,255,0)");
        g.fillStyle = puff; g.fillRect(0, 0, s, s);
      }
    });
  }

  setup();
  window.BikeSpot = { show, update: (list, isKnown) => update(list, isKnown !== false, false) };

  // Standalone preview with made-up occupancy that keeps changing.
  const params = new URLSearchParams(location.search);
  if (params.has("kind")) {
    const count = Number(params.get("slots") || 10);
    const demo = Array.from({ length: count }, (_, i) => ({ id: String(i + 1), label: i + 1, occupied: Math.random() < 0.55 }));
    const lat = Number(params.get("lat") || 47.48683), lon = Number(params.get("lon") || 7.59919);
    const heading = Number(params.get("heading") || 0) * Math.PI / 180;
    // An outline whose first edge points along the rack, like the backend's.
    const dLat = -Math.sin(heading) / 111320, dLon = Math.cos(heading) / (111320 * Math.cos(lat * Math.PI / 180));
    show({ kind: params.get("kind"), center: [lat, lon], polygon: [[lat, lon], [lat + dLat, lon + dLon]], slots: demo });
    setInterval(() => {
      const slot = demo[Math.floor(Math.random() * demo.length)];
      slot.occupied = !slot.occupied;
      update(demo, true, false);
    }, 2500);
  }
})();
