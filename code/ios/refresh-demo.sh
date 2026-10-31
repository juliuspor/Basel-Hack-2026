#!/bin/sh
# Refreshes the app's built-in demo data from a running backend and the
# scene generator's output. Run from anywhere:
#   code/ios/refresh-demo.sh [backend url]
set -e
cd "$(dirname "$0")"
URL="${1:-http://localhost:8000}"
OUT=../scene-generator/out
DEMO=BikeSlot/Demo

mkdir -p "$DEMO"
python3 - "$URL" "$DEMO/demo-areas.json" <<'PY'
import json, sys, urllib.request
url, target = sys.argv[1], sys.argv[2]
get = lambda path: json.load(urllib.request.urlopen(url + path))
details = [get(f"/areas/{area['id']}") for area in get("/areas")]
for detail in details:
    detail["analyzer"] = "demo"
json.dump(details, open(target, "w"), indent=2)
print(f"wrote {len(details)} areas to {target}")
PY
cp "$OUT"/bike.usdz "$DEMO"/
for id in $(python3 -c "import json; print(' '.join(a['id'] for a in json.load(open('$DEMO/demo-areas.json'))))"); do
  cp "$OUT/$id.usdz" "$DEMO/"
done
ls -lh "$DEMO"
