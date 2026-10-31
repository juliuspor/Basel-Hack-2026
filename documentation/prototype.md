# Prototype: how it fits together and how to run it

```
Blender (code/scene-generator)                    Backend (code/backend)                 iOS app (code/ios)
  layouts/*.json ──▶ <area>.usdz, bike.usdz ───────▶ GET /models/*.usdz      3D spot view (three.js, in the app)
                └──▶ cameras/<area>/frames + camera.json
                                   │
  simulate.py (virtual cameras) ───┴─ POST /ingest/<area> (JPEG) ─▶ change check ─▶ vision provider
                                                                   └▶ slot states ─▶ GET /areas ─▶ map + status
```

- **Cameras are simulated.** `render_frames.py` renders each shelter from a fixed
  camera position as it fills up between 07:00 and 09:30. `simulate.py` posts
  those frames like an ESP32-CAM would and prints how many slots the backend got
  right.
- **Analysis.** The backend skips frames that barely changed, blacks out everything
  outside the parking area, then runs a vision provider (`VISION_PROVIDER`):
  - `claude`: a Claude vision model (`claude-haiku-5-5`), used when
    `ANTHROPIC_API_KEY` is set. It gets the frame with numbered tags on the slots.
  - `diff` otherwise: compares each slot's wheel-holder region with a
    frame of the empty shelter. Offline, free, and exact on the rendered frames.
- **Privacy.** Frames are only held in memory; the backend keeps slot states and timestamps.
- **App.** Flat map of the Endress+Hauser block in Reinach with a pin per bike
  spot showing its free slots (Endress+Hauser blue while any are free, red when
  full, grey until a camera reports). The four spots are the racks marked on
  the challenge's map: the bike garage on the north side, the long shelter at
  the bus stop on the east side, and curved shelters on the west (Kägenstrasse)
  and south (Christoph-Merian-Ring) sides. Tapping a pin opens a card with the
  counts, a 3D view button and cycling directions; pulling the card down
  shrinks it, pulling again dismisses it. The 3D view (`code/ios/BikeSlot/Spot/`,
  three.js) starts above a model of the block, built from
  `assets/campus-map/source.osm` by `python3 code/scene-generator/site_world.py`,
  and flies down until you stand in front of the rack: a glowing blue pad on
  every free slot and a bike on every taken one. Once landed the camera stays
  put. Spots without a camera show grey pads. Open
  `spot.html?kind=curved_shelter&slots=10&lat=47.48683&lon=7.59919&heading=0`
  from that folder in a browser to preview it with made-up slots. The
  binoculars button opens Apple Look Around at the street next to the spot
  where Apple has imagery (it needs internet, so it is hidden offline). The bus
  stop shelter stands on the position measured in
  `assets/campus-map/slots.json`; the other three are placed from the
  challenge's map.
- **Search.** The search bar on the map finds shelters by name and places or
  addresses through Apple Maps (biased to the area around the site). Picking a
  place drops a marker there, frames it with the nearby shelters, and opens the
  card of the closest shelter with free spots.

## Run it

Requirements: Blender 5.2, Python 3.13 or later (Homebrew), Xcode 27, XcodeGen.

```bash
brew install --cask blender && brew install xcodegen python@3.13
```

1. Build the models and simulated frames (about a minute):

```bash
code/scene-generator/build_all.sh
```

   If `blender` is not on your `PATH`, point the script at the app:

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender code/scene-generator/build_all.sh
```

2. Start the backend:

```bash
cd code/backend && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cd code/backend && .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

   To use the vision model, export `ANTHROPIC_API_KEY` first (or set
   `VISION_PROVIDER=claude`; `VISION_MODEL` picks another model).

3. Start the virtual cameras in a second terminal (one frame per area every 6 s):

```bash
cd code/backend && .venv/bin/python simulate.py --interval 6
```

4. Build and run the app. Open `code/ios/BikeSlot.xcodeproj` in Xcode and run it
   on a simulator, or after changing `project.yml`:

```bash
cd code/ios && xcodegen generate
```

   On a phone, pick your signing team in Xcode. Debug builds connect to the
   backend on the Mac that built them (its Wi-Fi address is written into the app
   at build time), so the phone must be on the same Wi-Fi and allowed Local
   Network access. Rebuild after the Mac changes networks, or set another
   address in the app's settings (gear icon).

   For UI work without steps 1 to 3, turn on **Demo data** in the app's settings
   or launch it with `-demoMode YES`.

How the parts are split between people, and how to add a vision model or a
cloud store, is in [architecture.md](architecture.md).

## Useful details

- `bikeslot://area/<id>` or the launch argument `-openArea <id>` opens an area directly.
- If code signing fails with "resource fork, Finder information, or similar
  detritus not allowed", the project sits in an iCloud-synced folder such as
  Desktop. Build with `-derivedDataPath` outside it, for example `/tmp/BikeSlotDD`.
- API: `GET /areas`, `GET /areas/<id>` (adds per-slot states), `POST /ingest/<id>`
  (JPEG body, optional `X-Camera-Time` header), `GET /models/<file>.usdz`, `GET /health`.
