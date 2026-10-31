# Challenge criteria checklist

How Easy+Hitch measures up against the
[Find my Bike Slot brief](https://www.baselhack.ch/challenges/placeholder-endress-hauser)
(summary in [`challenge.md`](challenge.md)). Status reflects the prototype as
described in [`prototype.md`](prototype.md) on 31 October 2026.

The event's own judging criteria are in [`judging.md`](judging.md).

Legend: ✅ working in the prototype · 🟡 partly there or simulated · ⬜ concept only

## Problem statement

> How might we help employees quickly find an available bicycle parking slot at
> our company site?

| | Answer |
|---|---|
| 🟡 | Riders see free slots per shelter on a map of the site before they arrive. The slot states come from camera frames analysed by the backend; the cameras are simulated so far. |

## Must-haves

None. The brief invites teams to deviate from the idea and be creative.

## Nice-to-haves

| Criterion | Status | How we cover it | Gap |
|---|---|---|---|
| Real-time or estimated slot availability | 🟡 | Backend analyses each camera frame per slot (vision model, or the offline reference-diff analyzer) and serves live slot states via `GET /areas`. | Frames come from virtual cameras; occupancy forecasts ("full by 7:52?") are concept only. |
| Directions to available parking | ✅ | Each shelter's card offers cycling directions. Searching for a place opens the card of the closest shelter with free spots. | Directions lead to the shelter, not to a specific free slot. |
| A simple mobile or web interface | ✅ | iOS app with a map of the site, a pin per shelter with its free spots, and green/red numbered slot markers in each shelter's 3D view. | — |
| Privacy friendly | ✅ | Frames stay in memory only; the backend stores slot states and timestamps. Before frames go to the vision model, everything outside the parking area is blacked out. | Real ESP32 frames should also be cropped or blurred on the device before upload. |
| A prototype, ideally with sensors | 🟡 | End-to-end prototype: frame ingest, analysis, app. `POST /ingest/<area>` accepts JPEGs the way an ESP32-CAM would send them. | No physical ESP32-CAM connected yet; `simulate.py` stands in for the cameras. |

## No-gos

| Rule | Status | How we comply |
|---|---|---|
| No storing faces, licence plates, or other personal data | ✅ | No frames are written to disk; only per-slot states and timestamps are kept. |
| No identifying or tracking individual persons | ✅ | The analyzers only answer "bike or no bike" per slot. Nothing links a slot to a person or follows anyone between frames. |

## Tags and resources

| Item | Status | Notes |
|---|---|---|
| #image recognition | ✅ | Per-slot bike detection by a vision model, with an offline reference-diff fallback. |
| #embedded | ⬜ | ESP32-CAM firmware (capture, on-device crop or blur, HTTPS post) is still to do. |
| Ten shared ESP32-CAM boards | ⬜ | Not yet claimed or integrated. |
| Reference photos of the parking areas | ✅ | 23 site photos from 29 October 2026 in `assets/`. |
| CHF 100 AI budget per team | 🟡 | Covers the optional vision-model analyzer (`ANTHROPIC_API_KEY`); the offline analyzer needs none. |

## Before judging

1. Connect at least one real ESP32-CAM to `POST /ingest/<area>`, cropping or blurring on the device.
2. Replace the placeholder shelter coordinates in `code/backend/data/areas.json` with the measured ones in `assets/campus-map/slots.json`.
3. Point riders to a specific free slot number once they reach the shelter.
