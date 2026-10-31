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

## How Easy+Hitch covers them

| Criterion | Our answer | Where it shows |
|---|---|---|
| Innovation | Spot-level availability (which exact spot is free), not just "the stand is full", delivered before you arrive. | Slide 1, demo |
| Impact | Less time circling at 7:45, more people choosing the bike, and occupancy data for facility planning. | Slide 1 |
| Technical depth | ESP32-CAM → API Gateway → PII scanner → Jev model → PostgreSQL → API → iOS app. Working backend with per-slot analysis. | Slide 3, live app |
| AI code review | Small, scoped Conventional Commits (see `AGENTS.md`); no generated files or secrets in the history. | Repository |
| Fair play | The PII scanner removes faces and plates before the Jev model sees a frame; no images stored, no tracking. Matches the challenge's no-gos. | Slide 3 |
| Pitch | Four slides, one story: problem, live demo, architecture, finale. Speaker notes per slide (press N). | `assets/pitch/index.html` |
| Demo | Prefer the live iOS app against the running backend; the phone mock on slide 2 is the fallback. | Slide 2 |

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
