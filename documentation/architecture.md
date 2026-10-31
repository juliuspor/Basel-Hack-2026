# Architecture: who owns what, and where the seams are

The prototype is split so the app, the backend, the vision models and the 3D
scenes can be worked on in parallel. Each part talks to the next through one
small, written-down interface.

```
 Camera (ESP32-CAM, or simulate.py)
   │  POST /ingest/{area}  JPEG
   ▼
 Backend (code/backend, FastAPI)
   ingest ─▶ change check ─▶ privacy mask ─▶ VisionProvider ─▶ StateStore
   read API (/areas, /areas/{id}) ◀── StateStore, AssetStore
   │
   │  API contract: documentation/api/openapi.json (from schemas.py)
   ▼
 iOS app (code/ios), or its built-in demo data
```

| Part | Folder | Interface it owns |
|---|---|---|
| App UI | `code/ios` | Uses the API contract; ships demo data |
| Backend API | `code/backend/app.py`, `schemas.py`, `storage.py` | The API contract; `StateStore`, `AssetStore` |
| Vision models | `code/backend/providers/` | `VisionProvider` |
| 3D scenes and simulated cameras | `code/scene-generator` | The per-area asset bundle |

## 1. App ↔ backend: the API contract

- `code/backend/schemas.py` defines every response the app reads. FastAPI turns
  it into an OpenAPI spec, exported to [`api/openapi.json`](api/openapi.json).
  A running backend also serves it at `/openapi.json` and as browsable docs at
  `/docs`.
- Fields are snake_case in JSON; the app converts them to camelCase.
- `model_url` is either a path on the backend (`/models/<id>.usdz`) or an
  absolute URL, so models can later come from S3 or a CDN.

Changing the contract (renaming, removing or retyping a field, or a new
endpoint the app needs) goes in one pull request that also:

1. regenerates the spec: `cd code/backend && .venv/bin/python export_openapi.py`
2. refreshes the app's demo data: `code/ios/refresh-demo.sh` (needs a running
   backend)
3. updates `code/ios/BikeSlot/Models.swift` if the app should use the change

Adding an optional field is safe: the app ignores fields it does not know.

## 2. App without a backend: demo mode

The app ships sample shelters (`code/ios/BikeSlot/Demo/`: JSON in the API's
format plus the USDZ models). In demo mode a random slot changes every four
seconds, so the UI has live updates to show. Turn it on with
**Settings → Demo data**, or launch with `-demoMode YES` (in Xcode: Scheme →
Run → Arguments). UI work then needs only Xcode.

In code, both the live backend and the demo implement `AreaService`
(`APIClient.swift`); `Backend.current` picks one.

## 3. Backend ↔ vision models: `VisionProvider`

A provider is a class with a `name` and
`analyze(image, camera) -> Result` (`providers/base.py`):

- `image` is already masked to the parking area. The backend applies the
  privacy mask before any provider is called, so a new provider cannot skip it.
- `camera` is the area's calibration: slot ids with their numbered tag position
  and pixel region, the parking area's region and a reference frame of the
  empty area.
- `Result` holds the occupied slot ids, whether a person is in view, and free-form
  `detail` (scores, token usage).

Available providers, picked with `VISION_PROVIDER`:

| Name | What it does | Needs |
|---|---|---|
| `diff` | Compares each slot with the empty reference frame | Nothing |
| `claude` | Asks a Claude vision model (`VISION_MODEL`, default `claude-haiku-5-5`) | `ANTHROPIC_API_KEY` |
| `auto` (default) | `claude` if a key is set, else `diff` | |

To add one (OpenAI, a model on AWS Bedrock, …):

1. Create `providers/<name>.py` with the class. Reuse `tagged_jpeg`, `prompt`,
   `result_schema` and `from_answer` from `base.py`, so every model gets the same
   image and question and they can be compared fairly.
2. Register it in `PROVIDERS` in `providers/__init__.py`. Import the SDK inside
   the class, so others do not need it installed.
3. Add the SDK to `requirements.txt`, and the name to the parametrized test in
   `tests/test_contract.py` to check it against the simulated frames.

The simulated frames carry the true state of every slot, so `simulate.py` (and
the test) measure each provider's accuracy.

## 4. Where state and assets live: `StateStore` and `AssetStore`

`storage.py` defines both interfaces and the local versions that run on a
laptop:

- `StateStore` keeps an `AreaState` per area: slot states, timestamps, frame
  counters. No images and nothing about people. `MemoryStateStore` loses it on
  restart; a cloud version (e.g. DynamoDB) is a new class with `get` and `put`.
- `AssetStore` reads the site list (`data/areas.json`), each area's layout,
  camera calibration and 3D model. `LocalAssetStore` reads the repo and
  `code/scene-generator/out`; a cloud version (e.g. S3) is a new class, and its
  `model_url` can return an absolute URL.

`STATE_STORE` and `ASSET_STORE` pick the implementation in `make_stores()`
(only `local` exists so far). Only `storage.py` should import cloud SDKs.

## 5. Scene generator ↔ backend: the area bundle

For each area, `code/scene-generator/build_all.sh` writes into `out/`:

- `<id>.usdz`: the 3D model, with empties named `slot_<id>` the app places
  markers on
- `cameras/<id>/camera.json` plus `empty.jpg`: calibration and reference frame
- `cameras/<id>/frame_*.jpg`: simulated camera frames with the true state

The layout itself is `code/scene-generator/layouts/<id>.json`. A new area needs
a layout, a build, and an entry in `code/backend/data/areas.json`.

## Checks

```bash
cd code/backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest
```

The tests fail when the exported spec or the app's demo data no longer match
the code, or when a provider misreads the simulated frames.
