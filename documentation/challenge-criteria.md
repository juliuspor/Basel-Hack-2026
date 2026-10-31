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
| Real-time or estimated slot availability | 🟡 | Backend analyses each camera frame per slot ([`ingest`](../code/backend/app.py#L125-L162); vision model, or the offline reference-diff analyzer) and serves live slot states via `GET /areas` ([`list_areas`](../code/backend/app.py#L109-L111)). | Frames come from virtual cameras; occupancy forecasts ("full by 7:52?") are concept only. |
| Directions to available parking | ✅ | Each shelter's card offers cycling directions ([`directions`](../code/ios/BikeSlot/MapScreen.swift#L331-L337)). Searching for a place opens the card of the closest shelter with free spots ([`go`](../code/ios/BikeSlot/MapScreen.swift#L93-L103)). | Directions lead to the shelter, not to a specific free slot. |
| A simple mobile or web interface | ✅ | iOS app with a map of the site, a pin per shelter with its free spots ([`AreaPin`](../code/ios/BikeSlot/MapScreen.swift#L131-L153)), and a 3D view that flies down into a model of the site and lands in front of the chosen rack, its free slots glowing green ([`SpotView`](../code/ios/BikeSlot/SpotView.swift#L9-L74)). | — |
| Privacy friendly | ✅ | Frames stay in memory only; the backend stores slot states and timestamps ([`AreaState`](../code/backend/storage.py#L21-L31)). Before frames go to the vision model, everything outside the parking area is blacked out ([`privacy_mask`](../code/backend/providers/base.py#L36-L41)). | Real ESP32 frames should also be cropped or blurred on the device before upload. |
| A prototype, ideally with sensors | 🟡 | End-to-end prototype: frame ingest, analysis, app. `POST /ingest/<area>` accepts JPEGs the way an ESP32-CAM would send them ([`client.post`](../code/backend/simulate.py#L43-L44)). | No physical ESP32-CAM connected yet; [`simulate.py`](../code/backend/simulate.py) stands in for the cameras. |

## No-gos

| Rule | Status | How we comply |
|---|---|---|
| No storing faces, licence plates, or other personal data | ✅ | No frames are written to disk; only per-slot states and timestamps are kept ([`ingest`](../code/backend/app.py#L125-L162)). Checked on 31 October 2026: 18 analysed frames left no file behind ([judging.md](judging.md#what-we-checked)). |
| No identifying or tracking individual persons | ✅ | The analyzers only answer "bike or no bike" per slot, plus one yes/no for "a person is in view" ([`Result`](../code/backend/providers/base.py#L23-L27)). Nothing links a slot to a person or follows anyone between frames. |

## Tags and resources

| Item | Status | Notes |
|---|---|---|
| #image recognition | ✅ | Per-slot bike detection by a vision model ([`ClaudeProvider`](../code/backend/providers/claude.py#L8-L41)), with an offline reference-diff fallback ([`DiffProvider`](../code/backend/providers/diff.py#L6-L29)). |
| #embedded | ⬜ | ESP32-CAM firmware (capture, on-device crop or blur, HTTPS post) is still to do. |
| Ten shared ESP32-CAM boards | ⬜ | Not yet claimed or integrated. |
| Reference photos of the parking areas | ✅ | 23 site photos from 29 October 2026 in `assets/`. |
| CHF 100 AI budget per team | 🟡 | Covers the optional vision-model analyzer (`ANTHROPIC_API_KEY`); the offline analyzer needs none. |

## Before judging

1. Connect at least one real ESP32-CAM to `POST /ingest/<area>`, cropping or blurring on the device.
2. Confirm shelter C's position on site (A and B already use the mapped positions in `assets/campus-map/slots.json`) and add the 45-slot north shelter.
3. Point riders to a specific free slot number once they reach the shelter.
