# Campus map data

Map data for the **Find my Bike Slot** map UI around Christoph-Merian-Ring, Reinach.

## Files

- `assets/campus-map/source.osm`: OpenStreetMap extract of the campus (bounds 47.4850–47.4906 N, 7.5942–7.6025 E), downloaded 30 October 2026. It holds the building footprints, streets, and the north bicycle shelter roof ([OSM way 1463536691](https://www.openstreetmap.org/way/1463536691), about 2.3 × 53 m).
- `assets/campus-map/slots.json`: one record per parking slot, with zone, slot number, status, local metres (`x` east, `y` north of 7.59825 E, 47.48785 N), and longitude/latitude.
  - `CMR_NORTH_01`: 45 slots in the long north shelter beside the Bruggrain bus stop, five per bay.
  - `CMR_SOUTH_02`: 20 slots in two curved shelters at the silver building's rounded corner on the south bend.

  Positions come from OSM, satellite imagery, and the site photos of 29 October 2026 (`assets/IMG_20261029_*.jpg`). The second south shelter's exact position is unverified. The `status` values are illustrative, not live data.

## Attribution

OpenStreetMap data © OpenStreetMap contributors, available under the Open Database License. Keep this attribution wherever the data or map tiles derived from it are shown.
