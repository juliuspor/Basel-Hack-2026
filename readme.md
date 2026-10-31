# Easy+Hitch: Find my Bike Slot

Our entry for **Find my Bike Slot**, the Endress+Hauser challenge at BaselHack
2026. See the [challenge brief](documentation/challenge.md) for the problem,
suggested features, available resources, and privacy restrictions.

Easy+Hitch shows riders which bike slots are free at the Endress+Hauser site
in Reinach before they arrive. A camera at each shelter sends frames to a
backend that reads every slot as taken or free and keeps only those states,
never the images. An iOS app shows a pin per shelter with its free spots,
cycling directions, and a 3D view of each shelter. The cameras are simulated
for now: Blender renders each shelter filling up over a morning.

## Repository

| Folder | Contents |
|---|---|
| [`code/backend`](code/backend) | FastAPI backend: frame ingest, privacy mask, vision analyzers, and the slot API |
| [`code/ios`](code/ios) | SwiftUI app: map, search, shelter cards, 3D view, and an offline demo mode |
| [`code/scene-generator`](code/scene-generator) | Blender scripts for the shelter models and simulated camera frames with ground truth |
| [`documentation`](documentation) | How it works and runs, the API contract, and how we meet the judging criteria |
| [`assets`](assets) | Site photos, campus map data, and the pitch deck |

## Documentation

- [How it fits together and how to run it](documentation/prototype.md)
- [Architecture: the parts, their seams, and the target architecture](documentation/architecture.md)
- [Judging criteria, with evidence from the code](documentation/judging.md)
- [Challenge checklist](documentation/challenge-criteria.md)
- [API contract (OpenAPI)](documentation/api/openapi.json)
- [Campus map data](documentation/campus-data.md)
- [Pitch deck](assets/pitch/index.html)

## Licence

MIT, see [license.txt](license.txt).
