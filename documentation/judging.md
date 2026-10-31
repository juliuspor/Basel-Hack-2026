# Judging criteria

BaselHack 2026 rates every project on these criteria, as presented at the event:

| Criterion | What it means |
|---|---|
| Innovation | A value proposition that stands out |
| Impact | Social, economic, and technical relevance |
| Technical depth | How well it is built |
| AI code review | Quality of the code and the commit history |
| Fair play | Staying within the hackathon rules |
| Pitch | Clear story, confident delivery |
| Demo | It works, live |

The sponsor's own challenge points are in [`challenge-criteria.md`](challenge-criteria.md).

This page shows how Easy+Hitch meets each criterion. Every claim links to the
code behind it, and [What we checked](#what-we-checked) lists the commands we
ran and their results. Anything not in the code yet is marked **planned**.
[`test_docs.py`](../code/backend/tests/test_docs.py) fails when a link on this
page points at a file that is gone, or at lines that no longer hold the named
code.

## At a glance

| Criterion | Our answer | Details |
|---|---|---|
| Innovation | Which exact slot is free, read from a camera image by a general vision model without training data | [Innovation](#innovation) |
| Impact | Less searching at 7:45, cheap cameras, model calls only on change, privacy by design | [Impact](#impact) |
| Technical depth | A working pipeline from camera frame to app, with swappable parts and tests | [Technical depth](#technical-depth) |
| AI code review | Every commit follows the format in `AGENTS.md`; the API contract and these docs are tested | [AI code review](#ai-code-review) |
| Fair play | Built during the event, the challenge's no-gos enforced in code, third parties credited | [Fair play](#fair-play) |
| Pitch | Four slides, one story, speaker notes and a timer | [Pitch](#pitch) |
| Demo | A live pipeline, an offline demo mode, and a fallback | [Demo](#demo) |

## Innovation

**Spot level, not "the stand is full".** The API reports every slot, not just
a count ([`Slot`](../code/backend/schemas.py#L31-L34),
[`AreaDetail`](../code/backend/schemas.py#L37-L42)). Tapping a spot flies,
like Google Earth, from above a three.js model of the Endress+Hauser block
(its buildings, streets and trees from OpenStreetMap) down to where you would
stand in front of the rack ([`show`](../code/ios/BikeSlot/Spot/spot.js#L178-L225)).
The rack is built for the spot's kind
([`curvedShelter`](../code/ios/BikeSlot/Spot/spot.js#L335-L364) and three
more), with a glowing blue pad on every free slot and a bike on every taken one
([`makeSlot`](../code/ios/BikeSlot/Spot/spot.js#L238-L255)), shown in the app by
[`SpotView`](../code/ios/BikeSlot/SpotView.swift#L7-L70). The card below keeps
only the free count ([`StatusCard`](../code/ios/BikeSlot/AreaDetailScreen.swift#L53-L86)).

**No training data.** The backend draws a numbered tag in front of every slot
([`draw_labels`](../code/backend/providers/base.py#L44-L55)) and asks a vision
model which numbers hold a bike
([`prompt`](../code/backend/providers/base.py#L69-L77)). The answer may only
contain those numbers ([`result_schema`](../code/backend/providers/base.py#L80-L90)),
so a new shelter needs a calibration, not a trained model.

**Simulated cameras with ground truth.** Blender renders each shelter filling
up between 07:00 and 09:30 from a fixed camera
([`ARRIVALS`](../code/scene-generator/render_frames.py#L28-L29)), measures
every slot's position in the image
([`calibrate`](../code/scene-generator/render_frames.py#L80-L98)), and saves
the true state of every slot with each frame
([`frames`](../code/scene-generator/render_frames.py#L140-L153)). Every
analyzer is scored against it before a real camera is mounted.

**Found before you arrive.** Search for the building you are cycling to, and
the app opens the closest shelter that still has room
([`go`](../code/ios/BikeSlot/MapScreen.swift#L93-L103)). Where Apple has
street-level imagery, the shelter's 3D view has a Look Around button that shows
the street next to it, so you recognise the place when you get there
([`MKLookAroundSceneRequest`](../code/ios/BikeSlot/AreaDetailScreen.swift#L44-L48),
[`lookAroundViewer`](../code/ios/BikeSlot/AreaDetailScreen.swift#L35-L43)).
Without imagery or offline, the button stays hidden.

Planned: occupancy forecasts ("full by 7:52?") and pointing to one free slot
on arrival.

## Impact

- **Social.** Riders stop circling full shelters at 7:45, which makes cycling
  to work easier to choose. Free and full are blue and red, which stay
  distinguishable with red-green colour blindness
  ([`Brand`](../code/ios/BikeSlot/Theme.swift#L3-L13)). Nobody is watched: the
  backend keeps slot states only (see [Fair play](#fair-play)).
- **Economic.** The design targets the low-cost ESP32 camera boards the
  challenge provides; the simulated frames use their 800×600 resolution
  ([`WIDTH`](../code/scene-generator/render_frames.py#L27)). Frames that barely
  changed skip the analysis
  ([`CHANGE_THRESHOLD`](../code/backend/app.py#L137-L147)), so a vision model
  is only paid for when the picture changes, for example when a bike arrives
  or leaves. The `diff` analyzer runs
  offline at no cost ([`DiffProvider`](../code/backend/providers/diff.py#L6-L29)).
- **Technical.** Each shelter's state carries timestamps and frame counters
  ([`AreaState`](../code/backend/storage.py#L21-L31)), the basis for occupancy
  statistics for facility planning (planned). The API is an open contract
  ([`openapi.json`](api/openapi.json)) that other tools can use.

Not measured yet: time saved per rider, or how many more people cycle.

## Technical depth

**A working pipeline.** A camera posts a JPEG; the backend checks it for
change, masks it, reads every slot, and stores the result
([`ingest`](../code/backend/app.py#L125-L162)). The app polls the read API
every two seconds ([`pollAreas`](../code/ios/BikeSlot/AreaStore.swift#L17-L27))
and updates the map, the cards, and the 3D view.

**Parts behind interfaces**, so the app, the backend, the vision models, and
the 3D scenes were built in parallel ([architecture.md](architecture.md)):

| Interface | Implementations |
|---|---|
| API contract: [`AreaSummary`](../code/backend/schemas.py#L12-L28) and the other models in `schemas.py`, exported to [`openapi.json`](api/openapi.json) | FastAPI routes in [`app.py`](../code/backend/app.py) |
| [`VisionProvider`](../code/backend/providers/base.py#L30-L33) | [`DiffProvider`](../code/backend/providers/diff.py#L6-L29) and [`ClaudeProvider`](../code/backend/providers/claude.py#L8-L41), picked by [`make_provider`](../code/backend/providers/__init__.py#L30-L38) |
| [`StateStore`](../code/backend/storage.py#L34-L37) and [`AssetStore`](../code/backend/storage.py#L57-L72) | [`MemoryStateStore`](../code/backend/storage.py#L40-L54) and [`LocalAssetStore`](../code/backend/storage.py#L75-L102) |
| [`AreaService`](../code/ios/BikeSlot/APIClient.swift#L5-L8) in the app | [`APIClient`](../code/ios/BikeSlot/APIClient.swift#L19-L62) and [`DemoService`](../code/ios/BikeSlot/Demo/DemoService.swift#L3-L52) |

The planned cloud version swaps parts behind these interfaces; the
[target architecture](architecture.md#6-from-the-prototype-to-the-target-architecture)
maps each one.

**Built for real conditions.**

- A person walking through hides slots, so the backend keeps the last slot
  states while someone is in view
  ([`person_present`](../code/backend/app.py#L156-L159)), and the app says so
  ([`personPresent`](../code/ios/BikeSlot/AreaDetailScreen.swift#L77-L81)).
- Model answers must match a JSON schema whose only allowed values are the tag
  numbers ([`result_schema`](../code/backend/providers/base.py#L80-L90)), and
  an answer that was cut off raises an error instead of being misread
  ([`stop_reason`](../code/backend/providers/claude.py#L37-L38)).
- State changes happen under a lock, and the store hands out copies
  ([`lock`](../code/backend/app.py#L151-L160),
  [`MemoryStateStore`](../code/backend/storage.py#L40-L54)).
- Bad input fails cleanly: a body that is not an image gets a 400
  ([`HTTPException`](../code/backend/app.py#L132-L135)), and model downloads
  cannot leave the model folder
  ([`model_file`](../code/backend/storage.py#L98-L102)).
- Map outlines are computed from each shelter's centre, heading, and size
  ([`footprint`](../code/backend/app.py#L42-L53)).
- The app runs from iOS 18 and uses Liquid Glass on iOS 26 or later
  ([`glassBackground`](../code/ios/BikeSlot/Glass.swift#L3-L31)). Debug builds
  find the backend on the Mac that built them
  ([`defaultURL`](../code/ios/BikeSlot/APIClient.swift#L20-L24),
  [`postBuildScripts`](../code/ios/project.yml#L38-L48)).

**Tested.** [`test_contract.py`](../code/backend/tests/test_contract.py) fails
when the exported API spec or the app's demo data drift from `schemas.py`,
when an unknown provider is accepted, or when a provider misreads a simulated
frame. [`test_docs.py`](../code/backend/tests/test_docs.py) checks the links
in the documentation. Results are in [What we checked](#what-we-checked).

## AI code review

**Commit history.** [`AGENTS.md`](../AGENTS.md) sets the rules: Conventional
Commits with a scope, small focused commits, linear history on `main`, and
only team members as authors. On 31 October 2026, at commit `7622cae`, all 18
commits on `main` matched the format, all were authored by three team members,
none carried AI attribution, and no keys or tokens were found anywhere in the
history. Anyone can rerun the checks:

```bash
git log --format=%s | grep -Ev '^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)\([a-z0-9]+(-[a-z0-9]+)*\)!?: \S(.*\S)?$'
git log --format='%an' | sort | uniq -c
git log --format=%B | grep -iE 'co-authored-by|generated with'
git log --all -p | grep -E 'sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY'
```

All but the second print nothing.

**Code quality.**

- The main modules open with what they are for and how they fit in
  ([app.py](../code/backend/app.py#L1-L14),
  [storage.py](../code/backend/storage.py#L1-L6),
  [providers/base.py](../code/backend/providers/base.py#L1-L14)). Comments
  explain why rather than what, for example why a threshold of 40
  ([`CHANGE_THRESHOLD`](../code/backend/app.py#L31-L33)) or why the sun comes
  from the camera side
  ([`sun.rotation_euler`](../code/scene-generator/render_frames.py#L55-L56)).
- Keys come from the environment only
  ([`make_provider`](../code/backend/providers/__init__.py#L30-L38)), and an
  analyzer's SDK is only imported when that analyzer is used
  ([`PROVIDERS`](../code/backend/providers/__init__.py#L23-L27)).
- Generated files stay out of git: the scene generator's `out/`, the Python
  virtual environment and caches, Xcode build folders, and macOS Finder files
  ([backend](../code/backend/.gitignore),
  [scene generator](../code/scene-generator/.gitignore),
  [iOS](../code/ios/.gitignore), [root](../.gitignore)). The API spec and the
  app's demo data are generated but committed on purpose, and the tests fail
  when they drift.

## Fair play

- **Built at the event.** The repository starts from the BaselHack template
  (`f33cc57`: the readme, the licence, and empty `code/`, `documentation/`,
  and `assets/` folders), and every commit is dated 30 or 31 October 2026
  (`git log --all --format=%ad --date=short | sort -u`).
- **Template structure.** Code is in `code/`, documentation in
  `documentation/`, and media in `assets/`, as the template asks
  ([`AGENTS.md`](../AGENTS.md)).
- **The challenge's no-gos hold in code.**
  - No images are kept. The ingest route decodes each frame in memory and
    stores only slot states, timestamps, and frame counters
    ([`ingest`](../code/backend/app.py#L125-L162)); the
    state has no field for images or people
    ([`AreaState`](../code/backend/storage.py#L21-L31)). The only file the
    backend code writes is the API spec, from a developer script
    ([`OUT`](../code/backend/export_openapi.py#L11-L16)).
  - Before any analyzer sees a frame, everything outside the parking area is
    blacked out ([`privacy_mask`](../code/backend/providers/base.py#L36-L41),
    applied in [`provider.analyze(privacy_mask(…))`](../code/backend/app.py#L150)).
  - Nobody is identified or tracked. An analyzer returns slot ids and a single
    yes or no for "a person is in view"
    ([`Result`](../code/backend/providers/base.py#L23-L27)). Nothing links a
    slot or a frame to a person.
- **Third parties credited.** Python packages are listed in
  [`requirements.txt`](../code/backend/requirements.txt). The deck bundles
  canvas-confetti with its [ISC licence](../assets/pitch/vendor/LICENSE-canvas-confetti).
  The app's 3D spot view bundles three.js r149 with its
  [MIT licence](../code/ios/BikeSlot/Spot/LICENSE-three.txt); its 3D world is
  built from the OpenStreetMap extract and credited on screen.
  The campus map data is OpenStreetMap data under the ODbL, attributed in
  [`campus-data.md`](campus-data.md#attribution). The Endress+Hauser symbol
  comes from endress.com and is used for the sponsor's own challenge. The
  diagrams are rendered with archify 3.2.0.
- **Sponsor resources.** The CHF 100 AI budget only pays for the optional
  `claude` analyzer; the default `diff` analyzer needs none.
- **Authorship.** Only real team members appear as authors or co-authors, with
  no AI attribution ([`AGENTS.md`](../AGENTS.md#attribution)).

Known limit: the mask keeps the parking area itself, so a person standing at
the rack stays in the masked frame. With the `claude` analyzer, that frame is
sent to Anthropic's API for one answer and is not stored by us; the default
`diff` analyzer never sends a frame anywhere. Planned: pixelate faces on the
camera board before upload.

## Pitch

The deck, [`assets/pitch/index.html`](../assets/pitch/index.html), has four
slides and one story: the 7:45 problem, the live demo, the pipeline, and a
finale. It runs offline in a browser; only its web fonts need a connection. Each slide has speaker notes
([`NOTES`](../assets/pitch/index.html#L322-L327), press N). Press T for a
three-minute timer that turns yellow at 2:30 and red at 3:00
([`setInterval`](../assets/pitch/index.html#L351-L355)). The run sheet is
[below](#3-minute-run-sheet).

## Demo

Three ways to show it, from most to least live:

1. **Live pipeline.** Build the scenes, start the backend and the virtual
   cameras, and run the app on a phone ([Run it](prototype.md#run-it)). The
   shelters fill up as [`simulate.py`](../code/backend/simulate.py) replays
   the morning.
2. **App only.** Turn on Settings → Demo data, or launch with `-demoMode YES`.
   Built-in shelters change every four seconds without a backend
   ([`Backend`](../code/ios/BikeSlot/APIClient.swift#L10-L16),
   [`DemoService`](../code/ios/BikeSlot/Demo/DemoService.swift#L3-L52)).
3. **Fallback.** The phone mock on slide 2 of the deck loops on its own.

A real ESP32-CAM uses the same route as the simulator
([`client.post`](../code/backend/simulate.py#L43-L44)); it needs a calibration
(`camera.json`) for its view of the shelter.

## What we checked

On 31 October 2026, on macOS with Python 3.14.7 and Blender 5.2.3, at commit
`7622cae` plus the changes that added this page:

| Check | How | Result |
|---|---|---|
| Scenes and camera frames | `build_all.sh` ([Run it](prototype.md#run-it), step 1) | 3 shelter models, the bike, and 11 frames per shelter in 21 s |
| Backend tests | `.venv/bin/python -m pytest` in `code/backend` | All 4 contract tests passed, including the `diff` analyzer on the rendered frames; every documentation link passed |
| Slot accuracy, end to end | Backend, then `simulate.py --once --interval 0` | 31 of 31 slots right at all 11 steps from 07:00 to 09:30 (341 of 341 readings), `diff` analyzer |
| Change check | Send the same frame again | `"analyzed": false`, `"change": 0.0` |
| Bad input | Not an image; unknown area; `/models/..%2Fapp.py` | 400; 404; 404 |
| No images on disk | Analyse 18 frames, then list files newer than a marker file | None in the repository or the temp folder |
| Commit history | The four commands under [AI code review](#ai-code-review) | Clean |

Not checked on this machine: the iOS build (no Xcode installed), the `claude`
analyzer (no API key), and a physical ESP32-CAM (none connected yet).

## Known gaps

| Gap | Where | Next step |
|---|---|---|
| Cameras are simulated | [`simulate.py`](../code/backend/simulate.py) | Connect one ESP32-CAM to `POST /ingest/<area>` and calibrate its view |
| Two of the four spots (bus stop shelter, bike garage) have no camera yet, so the app shows their slots as unknown | [`site`](../code/backend/app.py#L57-L79) | Calibrate a camera per spot |
| The west shelter, the south shelter and the garage are placed from the challenge's map of the racks, not measured | [`areas.json`](../code/backend/data/areas.json) | Measure them on site like the ones in [`slots.json`](../assets/campus-map/slots.json) ([how it was mapped](campus-data.md)) |
| State is lost when the backend restarts | [`MemoryStateStore`](../code/backend/storage.py#L40-L54) | DynamoDB behind `StateStore` (planned) |
| The app allows plain HTTP, to reach a laptop backend | [`NSAllowsArbitraryLoads`](../code/ios/project.yml#L34-L36) | HTTPS once the API is hosted |
| Tests run locally only, and the app has none | [`tests/`](../code/backend/tests) | Run pytest on every push |
| The licence still names the template placeholder | [`license.txt`](../license.txt) | Add every team member |

## 3-minute run sheet

| Time | Slide | Focus |
|---|---|---|
| 0:00–0:40 | Hello | Problem at 7:45, value proposition, impact |
| 0:40–2:00 | Demo | Live app (fallback: the phone mock) |
| 2:00–2:45 | Tech | Pipeline, privacy by design |
| 2:45–3:00 | Finale | One-line close while the hamster lands: "You ride, we find the spot." |

Press T in the deck to show the pitch timer; it turns yellow at 2:30 and red at 3:00.

## Before judging

1. Commit the open work in small, scoped Conventional Commits.
2. Test the live demo end to end on the presenting phone, with the mock as backup.
3. Rehearse with the timer at least twice.
4. Make slide 3 match the [target architecture](architecture.md#6-from-the-prototype-to-the-target-architecture):
   the deck shows API Gateway, a PII scanner, and PostgreSQL, while the
   diagrams and `storage.py` plan on-board face blur, an Ingest Lambda, and
   DynamoDB. Say on the slide which parts run today.
5. Add every team member to [`license.txt`](../license.txt).
