# Christoph-Merian-Ring 3D campus model

This Blender scene covers the full blocks in the supplied aerial view, including the main Christoph-Merian-Ring corridor, the surrounding streets, and the two user-marked heart locations. It is a base for the **Find my Bike Slot** app concept.

## Files

- `assets/campus-map/scene.blend`: editable Blender model
- `assets/campus-map/overview.png`: oblique overview
- `assets/campus-map/topdown.png`: north-up comparison view
- `assets/campus-map/ring-detail.png`: north heart and mapped bicycle roof
- `assets/campus-map/south-detail.png`: south heart and street bend
- `assets/campus-map/source.osm`: source map extract
- `code/blender/build_campus.py`: procedural rebuild script

The scene uses separate collections for ground, streets, buildings, Ring details, bicycle parking, trees, annotations, and cameras. `CMR_NORTH_01` and `CMR_SOUTH_02` are the two wayfinding IDs. The orange dashed line between them is a virtual route overlay.

## Scale and source accuracy

One Blender unit is one metre. Horizontal building footprints and road paths are projected from [OpenStreetMap](https://www.openstreetmap.org/copyright), extracted 30 October 2026. This gives a metric, approximately 1:1 plan of the mapped campus. It does **not** make the whole scene survey accurate. Most building heights, road widths, facades, rooftop units, and small details are estimates.

The north bicycle shelter roof uses [OSM way 1463536691](https://www.openstreetmap.org/way/1463536691), tagged as bicycle parking and `building=roof`. Its mapped footprint is about **2.7 × 53 m**, west of the north-south section of Christoph-Merian-Ring. Its height, posts, and rack count are illustrative; capacity is unverified. The north heart has been snapped from the approximate screenshot pin to the Ring centreline beside the roof.

The south heart is an approximate position on the southern Ring segment from the user-provided aerial screenshot. The reference material does not establish the dimensions or placement of a physical shelter there. Both hearts are virtual wayfinding icons; their size and height are intentionally exaggerated for visibility and are not proposed physical structures. The separate curved canopy study remains in `assets/bike-shelter-study/` and is not placed on the campus map without a verified location.

For construction, precise navigation, or live capacity, obtain surveyed building heights, curb and path geometry, the two parking zone boundaries, and an on-site rack inventory.

## Rebuild

From a fresh Blender file, run:

```sh
blender --background --python code/blender/build_campus.py
```

The script reads `source.osm` and writes the `.blend` and four PNGs to `assets/campus-map/`. It uses Blender's built-in Python API.

OpenStreetMap data © OpenStreetMap contributors, available under the Open Database License. Retain attribution if this model is redistributed.
