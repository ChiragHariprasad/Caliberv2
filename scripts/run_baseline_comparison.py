"""Run Priority B scientific validation across all cached FastF1 races and write reproducible JSON reports."""
from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

warnings.filterwarnings("ignore")

from pulse.analytics.baseline_comparison import run_full_validation_suite  # noqa: E402


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    cache_dir = root / "data" / "fastf1_cache"
    out_dir = root / "reports" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)

    suite = run_full_validation_suite(cache_dir)
    suite["generated_at_utc"] = datetime.now(UTC).isoformat()

    ablation_payload = {
        "generated_at_utc": suite["generated_at_utc"],
        "protocol": suite["protocol"],
        "ablation_study": suite["ablation_study"],
    }
    baseline_payload = {k: v for k, v in suite.items() if k != "ablation_study"}

    (out_dir / "baseline_comparison.json").write_text(json.dumps(baseline_payload, indent=2), encoding="utf-8")
    (out_dir / "ablation_study.json").write_text(json.dumps(ablation_payload, indent=2), encoding="utf-8")

    print("=== LORO Aggregate 6-Model Comparison (5 Full Cached FastF1 Races) ===")
    for name, m in suite["loro_aggregate_comparison"].items():
        print(
            f"  {name:30s} n={m['n_predicted']:4d} "
            f"MAE={m['weighted_mae_sec']:.4f}s RMSE={m['weighted_rmse_sec']:.4f}s "
            f"PI95={m['weighted_pi95_coverage']*100:.2f}% (width={m['weighted_pi95_width_sec']:.2f}s)"
        )
    print("\n=== Holdout Japan 2022 Comparison ===")
    for r in suite["holdout_split"]:
        print(f"  [{r['session_id']}]")
        for name, m in r["models"].items():
            if m["n_predicted"]:
                print(
                    f"    {name:28s} n={m['n_predicted']:3d} "
                    f"MAE={m['mae_sec']:.4f}s RMSE={m['rmse_sec']:.4f}s PI95={m['pi95_coverage']*100:.2f}%"
                )
    print("\n=== Pace Ablation Aggregate ===")
    for k, v in suite["ablation_study"]["pace_components"].items():
        print(f"  {k:24s} n={v['n_predicted']:4d} MAE={v['mae_sec']:.4f}s RMSE={v['rmse_sec']:.4f}s PI95={v['pi95_coverage']*100:.2f}%")
    print("\n=== Shrinkage Ablation ===", suite["ablation_study"]["shrinkage_estimation"])
    print("=== SIA/Fusion Gate Ablation ===", suite["ablation_study"]["sia_gating_and_consequence_fusion"])


if __name__ == "__main__":
    main()
