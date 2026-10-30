# Scene generator

Blender scripts in [`code/scene-generator`](../code/scene-generator) that turn a
parking-area layout into a USDZ model for the iOS app's 3D view.

## Requirements

- Blender 5.2 (`brew install --cask blender`), run without a window (`-b`)

## Usage

From `code/scene-generator`:

```bash
blender -b --factory-startup -P generate_area.py -- layouts/curved-shelter-a.json out --occupied r1_03,r1_04,r1_08
```

```bash
blender -b --factory-startup -P generate_bike.py -- out
```

Outputs in `out/` (ignored by git, regenerate as needed):

| File | Purpose |
|---|---|
| `<id>.usdz` | Empty structure plus slot markers, loaded by the app |
| `<id>.blend` | Same scene for fine-tuning in the Blender UI |
| `<id>-preview.png` | Render with bikes on `--occupied` slots and green/red status squares |
| `bike.usdz` | Low-poly bike the app places on occupied slots |

`--no-render` skips the preview.

`build_all.sh` runs everything for every layout, including the simulated camera
frames:

```bash
blender -b --factory-startup -P render_frames.py -- layouts/curved-shelter-a.json out/cameras
```

This writes `out/cameras/<id>/` with `empty.jpg`, `frame_00.jpg` to `frame_10.jpg`
(07:00 to 09:30, 800x600 like an ESP32-CAM) and `camera.json`. `camera.json`
holds the calibration the backend uses (each slot's label point and wheel-holder
region in pixels, plus the parking-area region kept by the privacy mask) and the
ground truth per frame, which only the simulator reads.

## Layout file

One JSON file per area in `layouts/`. Dimensions are in metres.

| Field | Meaning |
|---|---|
| `id` | File name and root prim name (hyphens become underscores in USD) |
| `kind` | Only `curved_shelter` is supported so far |
| `reference_photo` | Photo the model is based on |
| `shelter.length` / `depth` / `height` | Outer size; depth runs from the open front to the rear |
| `shelter.arches` / `front_posts` | Number of curved arches and front posts, evenly spaced |
| `racks[].slots` / `start` / `pitch` | Number of wheel holders, x of the first, spacing |
| `racks[].rear_offset` | Distance of the holders from the rear |
| `racks[].staggered` | Alternate low and high holders |

## Contract with the app

- Every parking spot is an empty Xform named `slot_<rack id>_<nn>`, for example
  `slot_r1_04`. It sits on the ground under the centre of a parked bike. Its
  custom properties `zone` and `kind` are exported as `userProperties:*`.
- The USD file is Y-up in metres. Only the root prim carries the rotation from
  Blender's Z-up, so slots and the bike share the same local axes.
- To show a parked bike, load `bike.usdz`, take its entity named `bike`, add it
  as a child of the slot entity and set its transform to identity. Checked in
  RealityKit: the bike lands on the ground with its front wheel in the holder.

```swift
let area = try await Entity(contentsOf: areaURL)
let bike = try await Entity(contentsOf: bikeURL).findEntity(named: "bike")!
let slot = area.findEntity(named: "slot_r1_04")!
slot.addChild(bike)
bike.transform = .identity
```

## Matching a real area

The default dimensions are estimates from
[`IMG_20261029_083823.jpg`](../assets/IMG_20261029_083823.jpg). To fit a real
shelter, measure it on site or match the photo's camera with fSpy, then adjust
the layout JSON and regenerate. Hand edits in the `.blend` are lost on the next
run, so move a hand-edited file out of `out/` before regenerating.
