#!/bin/sh
# Builds every area model, the bike asset and the simulated camera frames into out/.
set -e
cd "$(dirname "$0")"
BLENDER="${BLENDER:-blender}"

"$BLENDER" -b --factory-startup -P generate_bike.py -- out
seed=1
for layout in layouts/*.json; do
    "$BLENDER" -b --factory-startup -P generate_area.py -- "$layout" out --no-render
    "$BLENDER" -b --factory-startup -P render_frames.py -- "$layout" out/cameras --seed "$seed"
    seed=$((seed + 1))
done
