"""
Held-Out Causal Evaluation of PULSE Scientific F1 Pace, Tyre & Strategy Models.

Evaluates RollingCleanAirPaceEstimator, FuelCompensatedDegradationModel, and
PitWindowStrategySimulator strictly causally (lap-by-lap in chronological race order)
against all cached offline FastF1 Grand Prix datasets and writes reports/f1_scientific_eval.json.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

import fastf1

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pulse.analytics.pace_and_tyre import (  # noqa: E402
    FuelCompensatedDegradationModel,
    PitWindowStrategySimulator,
    RollingCleanAirPaceEstimator,
    normalize_compound,
)

CACHE_DIR = Path(r"E:\Caliberv2\data\fastf1_cache")
OUT_PATH = Path(r"E:\Caliberv2\reports\f1_scientific_eval.json")

RACES = [
    (2021, "British Grand Prix", "2021_british_gp"),
    (2021, "Saudi Arabian Grand Prix", "2021_saudi_arabian_gp"),
    (2021, "Abu Dhabi Grand Prix", "2021_abu_dhabi_gp"),
    (2022, "Monaco Grand Prix", "2022_monaco_gp"),
    (2022, "Japanese Grand Prix", "2022_japanese_gp"),
]


def evaluate() -> dict:
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    fastf1.Cache.offline_mode(True)

    results = []
    for year, gp_name, sid in RACES:
        sess = fastf1.get_session(year, gp_name, "R")
        sess.load(laps=True, telemetry=False, weather=False, messages=False)
        laps = sess.laps
        total_laps = int(laps["LapNumber"].max())
        df = laps.copy()
        df["lap_sec"] = df["LapTime"].dt.total_seconds()

        est = RollingCleanAirPaceEstimator()
        deg = FuelCompensatedDegradationModel()
        pit_sim = PitWindowStrategySimulator()

        err_legacy_76: list[float] = []
        err_model: list[float] = []
        cov_95: list[int] = []
        all_slope_comp: dict[str, list[float]] = {"S": [], "M": [], "H": []}
        all_slope_raw: dict[str, list[float]] = {"S": [], "M": [], "H": []}
        last_seen_stints: set[tuple[int, int]] = set()

        # Process chronologically lap by lap (cross-driver causal execution)
        for ln in sorted(df["LapNumber"].dropna().unique()):
            lap_int = int(ln)
            sub = df[df["LapNumber"] == ln]
            for _, row in sub.iterrows():
                dn = int(row["DriverNumber"])
                lap_sec = float(row["lap_sec"]) if row["lap_sec"] == row["lap_sec"] else None
                ts = str(row["TrackStatus"])
                neutralised = ts != "1"
                is_pit_in = row["PitInTime"] == row["PitInTime"]
                is_pit_out = row["PitOutTime"] == row["PitOutTime"]
                is_pit = is_pit_in or is_pit_out
                is_acc = bool(row["IsAccurate"])
                stint_id = int(row["Stint"]) if row["Stint"] == row["Stint"] else 1
                comp = normalize_compound(row["Compound"])
                tyre_age = int(row["TyreLife"]) if row["TyreLife"] == row["TyreLife"] else None

                pred = est.predict_baseline(sid, dn, target_lap=lap_int, compound=comp, stint_id=stint_id)

                if (
                    lap_sec is not None
                    and not neutralised
                    and not is_pit
                    and is_acc
                    and lap_int > 1
                ):
                    err_legacy_76.append(abs(lap_sec - 76.0))
                    if pred.baseline_sec is not None and pred.status == "STINT_ROLLING_CALIBRATED":
                        err_model.append(abs(lap_sec - pred.baseline_sec))
                        cov_95.append(1 if (pred.ci95_low_sec <= lap_sec <= pred.ci95_high_sec) else 0)

                if is_pit_in or is_pit_out:
                    pit_sim.record_pit_lap_observation(
                        sid,
                        dn,
                        lap_int,
                        lap_sec,
                        pred.baseline_sec,
                        is_pit_in=is_pit_in,
                        is_pit_out=is_pit_out,
                        neutralised=neutralised,
                    )

                est.observe_lap(
                    sid,
                    dn,
                    lap_int,
                    lap_sec if is_acc else None,
                    stint_id=stint_id,
                    compound=comp,
                    clean_air=not is_pit,
                    neutralised=neutralised,
                    total_laps=total_laps,
                    prior_prediction=pred,
                )
                deg.observe_lap(
                    sid,
                    dn,
                    lap_int,
                    lap_sec if is_acc else None,
                    compound=comp,
                    tyre_age=tyre_age,
                    stint_id=stint_id,
                    neutralised=neutralised,
                    pit_lap=is_pit,
                    total_laps=total_laps,
                )
                last_seen_stints.add((dn, stint_id))

        # Collect final per-stint raw vs fuel-compensated slopes
        for drv, slist in deg._stints.get(sid, {}).items():
            fuel_burn = est.predict_baseline(sid, drv).fuel_burn_sec_per_lap
            for st in slist:
                fit = deg._fit_stint(st, fuel_burn)
                if fit is not None and st.compound in all_slope_comp:
                    all_slope_comp[st.compound].append(fit[0])
                    all_slope_raw[st.compound].append(fit[2])

        green_loss, vsc_loss, pit_unc, pit_cal = pit_sim.get_pit_loss_calibration(sid, "VSC")
        n_pits = len(pit_sim._green_pit_losses.get(sid, []))
        rmse = math.sqrt(sum(e * e for e in err_model) / len(err_model)) if err_model else None

        compound_summary = {}
        for c in ["S", "M", "H"]:
            if all_slope_comp[c]:
                compound_summary[c] = {
                    "n_stints": len(all_slope_comp[c]),
                    "raw_median_slope": round(statistics.median(all_slope_raw[c]), 4),
                    "raw_positive_count": sum(1 for v in all_slope_raw[c] if v > 0),
                    "fuel_comp_median_slope": round(statistics.median(all_slope_comp[c]), 4),
                    "fuel_comp_positive_count": sum(1 for v in all_slope_comp[c] if v > 0),
                }

        row = {
            "year": year,
            "grand_prix": gp_name,
            "total_laps": total_laps,
            "evaluated_laps": len(err_model),
            "legacy_76s_mae_sec": round(sum(err_legacy_76) / len(err_legacy_76), 3),
            "pulse_v2_mae_sec": round(sum(err_model) / len(err_model), 3),
            "pulse_v2_rmse_sec": round(rmse, 3) if rmse is not None else None,
            "mae_reduction_pct": round((1.0 - (sum(err_model) / len(err_model)) / (sum(err_legacy_76) / len(err_legacy_76))) * 100.0, 2),
            "empirical_95pi_coverage_pct": round((sum(cov_95) / len(cov_95)) * 100.0, 2),
            "calibrated_green_pit_loss_sec": green_loss,
            "calibrated_vsc_pit_loss_sec": vsc_loss,
            "pit_samples": n_pits,
            "pit_calibration_status": pit_cal,
            "compound_degradation": compound_summary,
        }
        results.append(row)
        print(
            f"[{year} {gp_name:24s}] MAE: 76.0s={row['legacy_76s_mae_sec']:.3f}s -> "
            f"PULSEv2={row['pulse_v2_mae_sec']:.3f}s (-{row['mae_reduction_pct']:.1f}%), "
            f"PI95={row['empirical_95pi_coverage_pct']:.1f}%, PitLoss={green_loss:.2f}s (n={n_pits}, {pit_cal})"
        )
        for c, info in compound_summary.items():
            print(
                f"   Compound {c}: n={info['n_stints']:2d} | raw_med={info['raw_median_slope']:+.4f} ({info['raw_positive_count']}/{info['n_stints']} pos) "
                f"-> fuel_comp_med={info['fuel_comp_median_slope']:+.4f} ({info['fuel_comp_positive_count']}/{info['n_stints']} pos)"
            )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"benchmark": "FastF1_Causal_WalkForward_Phase3", "races": results}
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    evaluate()
