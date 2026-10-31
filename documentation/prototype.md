# Prototype: how it fits together and how to run it

```
Blender (code/scene-generator)                    Backend (code/backend)                 iOS app (code/ios)
  layouts/*.json ──▶ <area>.usdz, bike.usdz ───────▶ GET /models/*.usdz ─────────────────▶ 3D view (RealityKit)
                └──▶ cameras/<area>/frames + camera.json
                                   │
  simulate.py (virtual cameras) ───┴─ POST /ingest/<area> (JPEG) ─▶ change check ─▶ analyzer
                                                                   └▶ slot states ─▶ GET /areas ─▶ map + status
```

- **Cameras are simulated.** `render_frames.py` renders each shelter from a fixed
  camera position as it fills up between 07:00 and 09:30. `simulate.py` posts
  those frames like an ESP32-CAM would and prints how many slots the backend got
  right.
- **Analysis.** The backend skips frames that barely changed, then runs one of two analyzers:
  - `claude-haiku-5-5` (vision model) when `ANTHROPIC_API_KEY` is set. It blacks
    out everything outside the parking area and draws numbered tags on the slots
    before sending the frame.
  - `reference-diff` otherwise: compares each slot's wheel-holder region with a
    frame of the empty shelter. Offline, free, and exact on the rendered frames.
- **Privacy.** Frames are only held in memory; the backend keeps slot states and timestamps.
- **App.** Flat map of the Endress+Hauser site in Reinach with a pin per shelter
  showing its free spots (green while any are free, red when full). Tapping a pin
  opens a card with the counts, a 3D view button and cycling directions; pulling
  the card down shrinks it, pulling again dismisses it. The 3D view shows bikes on
  taken slots and green/red numbered markers. Shelter coordinates in
  `code/backend/data/areas.json` are placeholders.
- **Search.** The search bar on the map finds shelters by name and places or
  addresses through Apple Maps (biased to the area around the site). Picking a
  place drops a marker there, frames it with the nearby shelters, and opens the
  card of the closest shelter with free spots.

## Run it

Requirements: Blender 5.2, Python 3.13 (Homebrew), Xcode 27, XcodeGen.

```bash
brew install --cask blender && brew install xcodegen python@3.13
```

1. Build the models and simulated frames (about a minute):

```bash
code/scene-generator/build_all.sh
```

2. Start the backend:

```bash
cd code/backend && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cd code/backend && .venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
```

   To use the vision model, export `ANTHROPIC_API_KEY` first (or set
   `ANALYZER=claude`; `CLAUDE_MODEL` picks another model).

3. Start the virtual cameras in a second terminal (one frame per area every 6 s):

```bash
cd code/backend && .venv/bin/python simulate.py --interval 6
```

4. Build and run the app. Open `code/ios/BikeSlot.xcodeproj` in Xcode and run it
   on a simulator, or after changing `project.yml`:

```bash
cd code/ios && xcodegen generate
```

   On a phone, set the backend URL in the app (gear icon) to your laptop's
   address, e.g. `http://192.168.1.20:8000`, and pick your signing team in Xcode.

## Useful details

- `bikeslot://area/<id>` or the launch argument `-openArea <id>` opens an area directly.
- If code signing fails with "resource fork, Finder information, or similar
  detritus not allowed", the project sits in an iCloud-synced folder such as
  Desktop. Build with `-derivedDataPath` outside it, for example `/tmp/BikeSlotDD`.
- API: `GET /areas`, `GET /areas/<id>` (adds per-slot states), `POST /ingest/<id>`
  (JPEG body, optional `X-Camera-Time` header), `GET /models/<file>.usdz`, `GET /health`.
