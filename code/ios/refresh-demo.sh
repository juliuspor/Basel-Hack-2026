#!/bin/sh
# Refreshes the app's built-in demo data from a running backend. Run from anywhere:
#   code/ios/refresh-demo.sh [backend url]
set -e
cd "$(dirname "$0")"
URL="${1:-http://localhost:8000}"
DEMO=BikeSlot/Demo

mkdir -p "$DEMO"
python3 - "$URL" "$DEMO/demo-areas.json" <<'PY'
import json, random, sys, urllib.request
url, target = sys.argv[1], sys.argv[2]
get = lambda path: json.load(urllib.request.urlopen(url + path))
details = [get(f"/areas/{area['id']}") for area in get("/areas")]
for detail in details:
    detail["analyzer"] = "demo"
    if detail["updated_at"] is None:
        # No camera reports this spot yet; give the demo a plausible, fixed morning.
        rng = random.Random(detail["id"])
        for slot in detail["slots"]:
            slot["occupied"] = rng.random() < 0.6
        detail["occupied"] = sum(slot["occupied"] for slot in detail["slots"])
        detail["free"] = detail["capacity"] - detail["occupied"]
json.dump(details, open(target, "w"), indent=2)
print(f"wrote {len(details)} areas to {target}")
PY
ls -lh "$DEMO"
