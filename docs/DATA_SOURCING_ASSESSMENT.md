# CALIBRE — Data Sourcing, Licensing & Empirical Coverage Assessment

**Date:** 13 November 2026  
**Status:** Research and target data-governance reference. Capture coverage and external-source assertions were not runtime- or externally validated by the 22 November 2026 static audit.
**Regimes Governed:** PUBLIC, LICENSED, INSTITUTIONAL, LAB  

---

## 1. Overview & Data Regimes

CALIBRE's core principle regarding external data is **radical honesty about provenance and independence**:
- If two feeds derive from a shared upstream provider (e.g. FOM Live Timing), counting them as two independent sources is an epistemic falsehood. CALIBRE assigns both feeds to the same upstream closure (`F1_FOM_TIMING`), automatically recording `COMMON_CAUSE_EXPOSURE` and limiting source-corroboration depth to 1.
- No public dataset provides raw transponder loop pulse times or surveyed loop coordinates. These are only available in **INSTITUTIONAL** or **LAB** regimes.
- Public telemetry channels (FastF1, OpenF1) represent compressed, resampled (3–4 Hz) broadcasts, not proprietary 100 Hz team CAN-bus streams.

```text
+------------------+-----------------------------------------------+---------------------------------------------------------+
| Data Regime      | Underlying Sources                            | Epistemic Integrity & Allowable Claims                  |
+------------------+-----------------------------------------------+---------------------------------------------------------+
| **PUBLIC**       | FastF1 API, Jolpica-F1 (Ergast API), FIA Docs | Source depth = 1. Staleness, absence, consistency.     |
|                  | Open-source & public broadcast timing         | **No source-isolation claims.**                         |
+------------------+-----------------------------------------------+---------------------------------------------------------+
| **LICENSED**     | Contracted data feed (e.g. timing partner API)| Documented lineage; verifiable processing depth.       |
+------------------+-----------------------------------------------+---------------------------------------------------------+
| **INSTITUTIONAL**| Raw timing loop sensors, physical survey      | Genuinely disjoint origins (Loop A vs Loop B vs ECU).  |
|                  | Primary telemetry & FIA race control wire     | Full fault isolation and resilience k >= 1.            |
+------------------+-----------------------------------------------+---------------------------------------------------------+
| **LAB**          | Timing-system twin & seeded fault injector    | Independent by construction. Mechanism proofs.          |
+------------------+-----------------------------------------------+---------------------------------------------------------+
```

---

## 2. Source Evaluation & Licensing

### 2.1 FastF1 (v3.9.0+)
- **Provider / Upstream:** Accesses F1 live timing historical replay endpoints via public APIs.
- **Data Categories Covered:**
  - Lap times, sector times, speed-trap speeds.
  - Car telemetry: `Speed` (km/h), `RPM`, `Gear`, `Throttle` (0–100%), `Brake` (bool/numeric), `DRS` (0–14 status codes).
  - Positional coordinates: `X`, `Y`, `Z` (resampled, circuit-relative, $\approx 3.5\text{ Hz}$).
  - Track weather: air temp, track temp, humidity, pressure, wind speed, wind direction, rainfall.
  - Race control messages: chronological message log with lap/flag status.
- **Licensing & Terms:** Unofficial package. F1 live timing is proprietary to Formula One World Championship Limited. Permitted for non-commercial, personal, academic, and scientific research. Data redistribution prohibited; manifests store acquisition logic, content checksums, and normalized schema representations.
- **Limitations:** Cadence is capped at 3–4 Hz; brake channel is binary on many cars; position coordinates have high-frequency jitter requiring filtering; pit-lane loop zone entries are not explicitly exposed.

### 2.2 Jolpica-F1 / Ergast Open API
- **Provider / Upstream:** Open-source historical API continuing the Ergast database.
- **Data Categories Covered:**
  - Official race classification, grid positions, status (finished, retired, laps down).
  - Driver lap-by-lap timing (milliseconds resolution).
  - Pit stop records: lap, stop number, time of day, duration.
- **Licensing:** Creative Commons Attribution-NonCommercial-ShareAlike (CC BY-NC-SA).
- **Limitations:** No vehicle telemetry or positional data. Latency is non-real-time.

### 2.3 Official FIA Documents & Bulletins
- **Provider / Upstream:** Fédération Internationale de l'Automobile (FIA) Stewards & Race Director publications.
- **Data Categories Covered:**
  - Stewards decisions, summonses, infringement notices, protests, appeals.
  - Event notes, track limits notes, pit-lane speed limit declarations, technical delegate reports.
  - Official final classifications and grid documents.
- **Licensing:** Public regulatory publications.
- **Limitations:** Formatted as PDF text; requires deterministic parsing into structured reference facts.

---

## 3. Data Coverage Matrix for the 10-Race Corpus

| # | Race Event | Metadata & Classif. | Lap & Sector Timing | Car Telemetry (Speed/RPM/Pedals) | Position / GPS (X/Y/Z) | Track Geometry & Layout | Race Control Messages | Weather Samples | Official FIA Documents |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 01 | **2021 Abu Dhabi** | YES (FastF1/Jolpica) | YES (58 laps) | YES (20 cars, ~4Hz) | YES (X, Y, Z) | YES (Yas Marina 2021) | YES (Messages 1–62) | YES (Dry, 27°C) | YES (Docs 57, 58, WMSC) |
| 02 | **2021 Belgium** | YES (FastF1/Jolpica) | YES (1 lap official)| YES (Minimal, SC) | YES (Behind SC) | YES (Spa-Francorchamps) | YES (Red flags, aborts) | YES (Heavy Rain) | YES (Docs 18–23) |
| 03 | **2021 Saudi Arabia** | YES (FastF1/Jolpica) | YES (50 laps) | YES (Brake 69 bar) | YES (Jeddah Corniche) | YES (Jeddah 2021 v1) | YES (2 Red flags, VSC) | YES (Night, Dry) | YES (Doc 43 Brake-test) |
| 04 | **2021 Great Britain**| YES (FastF1/Jolpica) | YES (52 laps) | YES (Lap 1 Copse) | YES (Silverstone 2021) | YES (Silverstone GP) | YES (Lap 1 Red flag) | YES (Dry, 26°C) | YES (Docs 34, 49) |
| 05 | **2023 Austria** | YES (FastF1/Jolpica) | YES (71 laps) | YES (20 cars) | YES (T9/T10 GPS) | YES (Red Bull Ring) | YES (1200+ TL notes) | YES (Dry, 22°C) | YES (Docs 71, 73 Post-pen)|
| 06 | **2023 Australia** | YES (FastF1/Jolpica) | YES (58 laps) | YES (Restarts 1–3) | YES (Albert Park) | YES (Melbourne 2023) | YES (3 Red flags) | YES (Dry, 18°C) | YES (Docs 45, 52) |
| 07 | **2022 Japan** | YES (FastF1/Jolpica) | YES (28 laps) | YES (Gasly Crane) | YES (Suzuka GPS) | YES (Suzuka GP) | YES (Red flag, SC) | YES (Torrential Rain) | YES (Doc 36, FIA Report) |
| 08 | **2022 Monaco** | YES (FastF1/Jolpica) | YES (64 laps) | YES (Pit exit lines)| YES (Monaco GPS) | YES (Monaco Circuit) | YES (Start delay) | YES (Wet to Dry) | YES (Docs 56, 57 Lines) |
| 09 | **2024 United States** | YES (FastF1/Jolpica) | YES (56 laps) | YES (Lap 52 T12) | YES (COTA GPS) | YES (COTA Austin) | YES (Investigation) | YES (Dry, 28°C) | YES (Docs 69, 78 Apex) |
| 10 | **2023 Las Vegas** | YES (FastF1/Jolpica) | YES (FP1/Race) | YES (FP1 320km/h) | YES (Strip GPS) | YES (Las Vegas Strip) | YES (FP1 Cancel/Red) | YES (Night, 14°C) | YES (Doc 17 Valve cover) |

---

## 4. Normalization & Integrity Validation Pipeline

Every acquired raw event must pass through the canonical normalization gate before admission:
1. **Canonical Schema Validation:** Enforce typed time (`TimeClass`), unit tags (`km/h`, `s`, `celsius`, `ratio`), and integer-microsecond instants (`parse_instant()`).
2. **Deduplication:** Hash raw content via RFC 8785 canonical JSON; drop exact duplicates with `DUPLICATE_RECORD` diagnostic.
3. **Origin & Dependency Token Tagging:** Explicitly inject source origin (`F1_FOM_TIMING` or `CAR_ECU`) and processing origin (`FASTF1_PARSER_v3_9`).
4. **Scope Binding:** Assign composite keys (`session_id`, `driver_id`, `lap_number`, `sector_number`, `zone_id`).
5. **Quality Grading:** Assign initial quality grade (`HEALTHY`, `SUSPECT`, `UNKNOWN`, `DEGRADED`) based on channel completeness, sampling cadence, and jitter metrics.

