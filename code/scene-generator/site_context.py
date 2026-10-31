"""Surroundings of the south-bend shelters for the app's 3D view.

Reads the OpenStreetMap extract and writes the buildings, streets and street
trees within RADIUS metres of the site centre as plain local metres (x east,
y north). The app extrudes them into a diorama around the shelter you open, so
the shelters stand where they really are instead of on an empty plate. No
Blender needed.

Run: python3 code/scene-generator/site_context.py
"""

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parents[2]
OSM = ROOT / "assets/campus-map/source.osm"
OUT = ROOT / "code/ios/BikeSlot/Site/south-bend.json"

ORIGIN = (47.48690, 7.60010)  # same as Site.center in the app
RADIUS = 70
SILVER_BUILDING = "238805703"  # the industrial building the three shelters stand against
FLOOR = 3.8
ROAD_WIDTH = {"residential": 6.5, "service": 3.5}

# Street trees as seen in Apple Look Around (June 2026): a row between the silver
# facade and the parking along the south Ring, and a few on the east side.
TREES = [(x, -7.8) for x in range(-50, -17, 8)] + [(11.0, y) for y in range(18, 43, 8)]


def local(lat, lon):
    return (round((lon - ORIGIN[1]) * 111320 * math.cos(math.radians(ORIGIN[0])), 2),
            round((lat - ORIGIN[0]) * 111320, 2))


def main():
    root = ET.parse(OSM).getroot()
    nodes = {n.get("id"): local(float(n.get("lat")), float(n.get("lon"))) for n in root.iter("node")}
    buildings, roads = [], []
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.iter("tag")}
        points = [nodes[nd.get("ref")] for nd in way.iter("nd") if nd.get("ref") in nodes]
        if not points or min(math.hypot(*p) for p in points) > RADIUS:
            continue
        if "building" in tags and tags["building"] != "roof":
            silver = way.get("id") == SILVER_BUILDING
            buildings.append({"outline": points[:-1] if points[0] == points[-1] else points,
                              "floors": 4 if silver else 2, "style": "silver" if silver else "plain"})
        elif tags.get("highway") in ROAD_WIDTH:
            roads.append({"line": points, "width": ROAD_WIDTH[tags["highway"]]})

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"origin": ORIGIN, "floor_height": FLOOR, "buildings": buildings,
                               "roads": roads, "trees": TREES}, separators=(",", ":")))
    print(f"wrote {len(buildings)} buildings, {len(roads)} roads, {len(TREES)} trees to {OUT}")


if __name__ == "__main__":
    main()
