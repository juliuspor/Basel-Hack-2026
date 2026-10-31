# three.js prototype: 3D world of Endress+Hauser

An archived prototype, not part of the app. It is a low-poly, street-level
model of Christoph-Merian-Ring between the two bicycle stations at
Endress+Hauser, built directly in three.js: you ride down the Ring and see
which spots at each stand are free (green) or taken (red). The team dropped
the 3D world for the web maps view; this folder keeps it runnable for
reference.

## Run it

Serve the `assets/` folder, because the page also reads the shared
OpenStreetMap extract in `assets/campus-map/`:

```sh
python3 -m http.server 8139 --bind 127.0.0.1 --directory assets
```

Then open
<http://localhost:8139/threejs-prototype-3d-world-of-endress-hauser/index.html>.
three.js r170 loads from jsDelivr, so the page needs internet access.

## Views

- **Ride north → south**: the camera rides the right-hand side of the Ring
  from Bruggrain to the south bend, slowing and turning towards each stand.
- **North stand / South stand**: fixed rider's-eye views of each station,
  with mouse orbit.
- **Free look**: overview with orbit controls.

`window.__ring` exposes `stations` (free and total counts per zone) and
`setMode(view)` for checks.

## Sources

- [`main.js`](main.js) builds everything at load time:
  - [`../campus-map/source.osm`](../campus-map/source.osm) supplies the
    roads, building footprints, the north shelter roof (OSM way 1463536691),
    and mapped trees. © OpenStreetMap contributors, ODbL.
  - [`roof-colors.json`](roof-colors.json) supplies the roof colours.
- Facades are textures drawn on canvases from patterns observed in Google
  Street View (2023-2024), listed in `FACADES`. No imagery is copied.
  Buildings away from the Ring get a generic punched-window facade.
- Cars, trees, shrubs, street lamps, and the bus stop pole are Kenney models
  in [`kenney/`](kenney/), CC0 (each kit has its `License.txt`). Car paint and
  tree crowns are recoloured in code.
- Shelters, racks, bicycles, kerbs, and road markings are generated in code
  from the 29 October 2026 site photos.
- three.js r170 (MIT licence) loads from jsDelivr and is not vendored here.
- Slot occupancy is seeded and illustrative: 45 slots north, 20 south. No
  camera or sensor feeds this prototype.
