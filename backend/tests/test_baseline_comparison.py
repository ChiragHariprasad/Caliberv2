"""Regression checks for Priority B baseline comparison and zero-leakage protocol."""
from __future__ import annotations

import asyncio

from pulse.analytics.baseline_comparison import (
    CausalLapRecord,
    _ablate_sia_and_fusion_gating,
    evaluate_all_baselines_on_race,
)
from pulse.contracts import CleanAirStatus


def _synth_race(records: list[CausalLapRecord], sid: str = "synth-leak") -> dict:
    return {"session_id": sid, "year": 2022, "gp_name": "Test", "total_laps": 50, "records": records}


def test_zero_future_leakage_across_all_6_baselines():
    """Altering or appending future laps after lap k must never change predictions up to lap k."""
    base_recs = [
        CausalLapRecord("s1", 1, ln, 90.0 - 0.05 * ln, 1, "M", ln, 1, 2.5, CleanAirStatus.CLEAN_AIR_CONFIRMED, False, False, 50)
        for ln in range(2, 12)
    ]
    prefix_res = evaluate_all_baselines_on_race(_synth_race(list(base_recs)), return_points=True)

    # Append extreme wild outlier laps in the future (laps 12..16) and alter future compound/stint
    extended_recs = list(base_recs) + [
        CausalLapRecord("s1", 1, ln, 125.0, 2, "H", 1, 1, 2.5, CleanAirStatus.CLEAN_AIR_CONFIRMED, False, False, 50)
        for ln in range(12, 17)
    ]
    extended_res = evaluate_all_baselines_on_race(_synth_race(extended_recs), return_points=True)
    for m_name in prefix_res["models"]:
        assert prefix_res["models"][m_name]["n_target_laps"] == 10
        assert prefix_res["models"][m_name]["mae_sec"] is not None
        pref_pts = prefix_res["points"][m_name]
        ext_pts = extended_res["points"][m_name][: len(pref_pts)]
        assert len(ext_pts) == len(pref_pts)
        for p1, p2 in zip(pref_pts, ext_pts):
            assert (p1.pred_sec, p1.ci95_low_sec, p1.ci95_high_sec) == (p2.pred_sec, p2.ci95_low_sec, p2.ci95_high_sec)

    # Verify strict clean-air requirement: UNKNOWN intervals are NOT targets or baseline inputs for revised_pulse
    unk_recs = [
        CausalLapRecord("s2", 4, ln, 92.0, 1, "M", ln, 4, None, CleanAirStatus.CLEAN_AIR_UNKNOWN, False, False, 50)
        for ln in range(2, 10)
    ]
    unk_res = evaluate_all_baselines_on_race(_synth_race(unk_recs, "s2"))
    assert unk_res["models"]["revised_pulse"]["n_predicted"] == 0


def test_sia_and_fusion_ablation_eliminates_false_confirmations():
    res = asyncio.run(_ablate_sia_and_fusion_gating())
    assert res["phase_i_strict_sia_and_fusion_gate"]["fpr"] == 0.0
    assert res["phase_i_strict_sia_and_fusion_gate"]["precision"] == 1.0
    assert res["pre_phase_i_no_calibration_gate"]["fpr"] > res["phase_i_strict_sia_and_fusion_gate"]["fpr"]


def test_openf1_causal_loader_no_leakage_and_stint_bootstrap(tmp_path):
    """OpenF1 causal reconstruction must preserve prefix invariance and cluster bootstrap CIs."""
    import json
    from pulse.analytics.generalization_phase_j import (
        cluster_bootstrap_metrics,
        load_openf1_causal_laps,
        paired_common_support_comparison,
    )

    bundle = {
        "year": 2024,
        "name": "test_gp",
        "session_key": 9999,
        "drivers": [{"driver_number": 1, "team_name": "Red Bull Racing"}, {"driver_number": 4, "team_name": "McLaren"}],
        "stints": [
            {"driver_number": 1, "stint_number": 1, "lap_start": 1, "lap_end": 12, "compound": "MEDIUM", "tyre_age_at_start": 0},
            {"driver_number": 4, "stint_number": 1, "lap_start": 1, "lap_end": 12, "compound": "MEDIUM", "tyre_age_at_start": 0},
        ],
        "pit": [],
        "weather": [{"date": "2024-06-01T13:00:00+00:00", "rainfall": 0}],
        "race_control": [],
        "laps": [
            {
                "driver_number": dn,
                "lap_number": ln,
                "date_start": f"2024-06-01T13:{ln:02d}:{dn:02d}+00:00",
                "lap_duration": 89.0 - 0.04 * ln + (0.0 if dn == 1 else 0.5),
                "is_pit_out_lap": False,
            }
            for ln in range(1, 9)
            for dn in (1, 4)
        ],
    }
    p_base = tmp_path / "base.json"
    p_base.write_text(json.dumps(bundle), encoding="utf-8")
    race_base = load_openf1_causal_laps(p_base)
    res_base = evaluate_all_baselines_on_race(race_base, return_points=True)

    # Append chaotic future laps & SC deployment strictly after lap 8 ends: prefix predictions on laps 1..8 must match identically
    bundle_ext = json.loads(json.dumps(bundle))
    bundle_ext["race_control"].append({"date": "2024-06-01T13:10:00+00:00", "category": "SafetyCar", "flag": None, "message": "SAFETY CAR DEPLOYED"})
    for ln in range(9, 12):
        for dn in (1, 4):
            bundle_ext["laps"].append({
                "driver_number": dn,
                "lap_number": ln,
                "date_start": f"2024-06-01T13:{ln:02d}:{dn:02d}+00:00",
                "lap_duration": 135.0,
                "is_pit_out_lap": False,
            })
    p_ext = tmp_path / "ext.json"
    p_ext.write_text(json.dumps(bundle_ext), encoding="utf-8")
    race_ext = load_openf1_causal_laps(p_ext)
    assert race_ext["had_sc_or_vsc"] is True
    for r1, r2 in zip(race_base["records"], race_ext["records"][: len(race_base["records"])]):
        assert (
            r1.session_id, r1.driver_number, r1.lap_number, r1.lap_sec,
            r1.stint_id, r1.compound, r1.tyre_age, r1.position,
            r1.interval_sec, r1.clean_air_status, r1.is_pit, r1.neutralised,
        ) == (
            r2.session_id, r2.driver_number, r2.lap_number, r2.lap_sec,
            r2.stint_id, r2.compound, r2.tyre_age, r2.position,
            r2.interval_sec, r2.clean_air_status, r2.is_pit, r2.neutralised,
        )
    res_ext = evaluate_all_baselines_on_race(race_ext, return_points=True)
    assert res_ext["points"]["revised_pulse"][: len(res_base["points"]["revised_pulse"])] == res_base["points"]["revised_pulse"]

    boot = cluster_bootstrap_metrics(res_base["points"]["revised_pulse"], n_boot=200, seed=42)
    assert boot["n_predicted"] > 0 and boot["mae_ci95"][0] <= boot["mae_sec"] <= boot["mae_ci95"][1]
    pair = paired_common_support_comparison(res_base["points"], n_boot=200, seed=42)
    assert pair["n_common"] == boot["n_predicted"]
