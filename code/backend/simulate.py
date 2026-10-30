"""Virtual cameras: replay rendered frames to the backend as if ESP32s sent them.

Every area steps through its morning (07:00 to 09:30) in lockstep, one frame
per interval, then starts over. After each step it compares the backend's
state with the frames' ground truth and prints the accuracy.

Run: .venv/bin/python simulate.py [--interval 6] [--url http://localhost:8000]
"""

import argparse
import json
import time
from pathlib import Path

import httpx

CAMERAS = Path(__file__).parent.parent / "scene-generator" / "out" / "cameras"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--interval", type=float, default=6.0, help="seconds per frame")
    parser.add_argument("--once", action="store_true", help="play one morning, then stop")
    args = parser.parse_args()

    cameras = [json.loads(p.read_text()) for p in sorted(CAMERAS.glob("*/camera.json"))]
    steps = max(len(c["frames"]) for c in cameras)
    client = httpx.Client(base_url=args.url, timeout=60)
    print(f"{len(cameras)} virtual cameras, {steps} frames each, every {args.interval}s")

    while True:
        for step in range(steps):
            started = time.time()
            correct = total = 0
            for camera in cameras:
                frame = camera["frames"][min(step, len(camera["frames"]) - 1)]
                body = (CAMERAS / camera["area"] / frame["file"]).read_bytes()
                try:
                    client.post(f"/ingest/{camera['area']}", content=body,
                                headers={"Content-Type": "image/jpeg", "X-Camera-Time": frame["time"]})
                    state = client.get(f"/areas/{camera['area']}").json()
                except httpx.HTTPError as error:
                    print(f"{camera['area']}: backend unreachable ({error})")
                    continue
                truth = set(frame["occupied"])
                for slot in state["slots"]:
                    correct += slot["occupied"] == (slot["id"] in truth)
                    total += 1
            print(f"{frame['time']}  slots correct {correct}/{total}", flush=True)
            time.sleep(max(0.0, args.interval - (time.time() - started)))
        if args.once:
            break


if __name__ == "__main__":
    main()
