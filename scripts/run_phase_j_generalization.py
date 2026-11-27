"""Run Phase J extended scientific generalization & stint-level block bootstrap validation."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pulse.analytics.generalization_phase_j import run_extended_generalization_suite


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    result = run_extended_generalization_suite(
        root / "data" / "fastf1_cache",
        root / "data" / "openf1_cache",
        n_boot=2000,
    )
    out = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        **result,
    }
    out_path = root / "reports" / "benchmarks" / "phase_j_generalization.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("Corpus:", out["corpus_summary"]["total_races_loaded"], "races loaded")
    print("\n--- LORO-5 Investigation (revised vs existing) ---")
    inv = out["loro_5_race_investigation"]
    for m in ("revised_pulse", "existing_fuel_compensated", "rolling_clean_air_median", "circuit_normalized_regression"):
        row = inv["stint_bootstrap_models"][m]
        print(f"  {m:30s} n={row['n_predicted']:4d} MAE={row['mae_sec']} {row['mae_ci95']} RMSE={row['rmse_sec']} {row['rmse_ci95']} PI95={row['pi95_coverage']} {row['pi95_coverage_ci95']}")
    cs5 = inv["common_support_revised_vs_existing"]
    print(f"  50-lap abstention analysis -> n={cs5['abstained_by_a_predicted_by_b_count']}, existing MAE on those laps={cs5['b_performance_on_a_abstentions']['mae_sec']}, common_delta={cs5['paired_delta_mae_a_minus_b']} CI95={cs5['paired_delta_mae_stint_ci95']}")

    print("\n--- Unseen External 2023-2024 (11 OpenF1 races, zero params fit on 2023-2024) ---")
    for m, row in out["unseen_external_2023_2024_summary"].items():
        print(f"  {m:30s} n={row['n_predicted']:4d} MAE={row['mae_sec']} {row['mae_ci95']} PI95={row['pi95_coverage']} {row['pi95_coverage_ci95']}")
    cs23 = out["unseen_external_2023_2024_common_support"]
    print(f"  Common-support delta (revised - existing) = {cs23['paired_delta_mae_a_minus_b']} CI95={cs23['paired_delta_mae_stint_ci95']} (n_common={cs23['n_common']})")

    print("\n--- Walk-Forward (15 unseen chronological folds 2021-2024) ---")
    for m, row in out["walk_forward_summary"].items():
        print(f"  {m:30s} n={row['n_predicted']:4d} MAE={row['mae_sec']} {row['mae_ci95']} PI95={row['pi95_coverage']} {row['pi95_coverage_ci95']}")


if __name__ == "__main__":
    main()
