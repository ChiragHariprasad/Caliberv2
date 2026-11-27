# F1 track map geometry update

This package updates the ten supplied JSON maps using the corresponding GeoJSON `LineString` geometries in the MIT-licensed `bacinger/f1-circuits` repository. The source files are OSM-derived.

Repository: https://github.com/bacinger/f1-circuits
License: MIT (`LICENSE.md` in the repository)

## Geometry update

The source longitude/latitude vertices were projected locally with an equirectangular projection and uniformly scaled into each JSON file's existing `view_box`. The existing `LOCAL_NORMALIZED_1000` coordinate system, view box, layout identifiers, circuit metadata, track length values, travel direction, and sectors' progress values were retained. The centreline vertices come from the corresponding source GeoJSON circuit ID.

## Important accuracy boundary

The referenced repository supplies the circuit centreline only. It does not provide surveyed road-edge boundaries, pit-lane geometry, DRS zone definitions, or official corner/apex metadata. To avoid leaving stale geometry in the new coordinate frame, `inner_boundary`, `outer_boundary`, `pit_lane.path`, and `drs_zones` were cleared. Existing named corner labels and apex-speed values were retained; their marker positions were remapped by their along-track progress on the previous schematic centreline and are **not independently verified** against an official FIA turn map. Sector checkpoints and the start/finish marker were reprojected to the new path.

Consequently, the new centreline is source-derived and detailed, but this package should not be described as a complete FIA-homologated survey of every track feature.

## Source file mapping

| JSON | GeoJSON source ID |
|---|---|
| `albert_park.json` | `au-1953` |
| `cota.json` | `us-2012` |
| `jeddah.json` | `sa-2021` |
| `las_vegas.json` | `us-2023` |
| `monaco.json` | `mc-1929` |
| `red_bull_ring.json` | `at-1969` |
| `silverstone.json` | `gb-1948` |
| `spa.json` | `be-1925` |
| `suzuka.json` | `jp-1962` |
| `yas_marina.json` | `ae-2009` |

The `geometry_source`, `geometry_notes`, and `checksum_sha256` fields in each JSON record provenance and caveats.
