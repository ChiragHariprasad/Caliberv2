"""Phase J Independent Scientific Generalization & Cluster-Bootstrap Uncertainty Module."""
from __future__ import annotations

from bisect import bisect_right
from datetime import datetime
import json
import math
from pathlib import Path
import random
import statistics
from typing import Any

from pulse.analytics.baseline_comparison import (
    CALIBRATION_RACES,
    HOLDOUT_RACES,
    CausalLapRecord,
    LapPredictionPoint,
    _eval_regression_fit,
    evaluate_all_baselines_on_race,
    load_fastf1_causal_laps,
)
from pulse.analytics.pace_and_tyre import (
    CleanAirStatus,
    normalize_compound,
    resolve_clean_air_status,
)


OPENF1_CHRONO_ORDER: list[tuple[int, str, str, str]] = [
    (2023, "austria", "2023 Austrian Grand Prix", "High-Speed"),
    (2023, "great_britain", "2023 British Grand Prix", "High-Speed"),
    (2023, "netherlands", "2023 Dutch Grand Prix", "Technical"),
    (2023, "singapore", "2023 Singapore Grand Prix", "Street"),
    (2023, "japan", "2023 Japanese Grand Prix", "Technical"),
    (2024, "saudi_arabia", "2024 Saudi Arabian Grand Prix", "Street"),
    (2024, "monaco", "2024 Monaco Grand Prix", "Street"),
    (2024, "canada", "2024 Canadian Grand Prix", "Technical"),
    (2024, "great_britain", "2024 British Grand Prix", "High-Speed"),
    (2024, "monza", "2024 Italian Grand Prix", "High-Speed"),
    (2024, "brazil", "2024 Sao Paulo Grand Prix", "Technical"),
]

CIRCUIT_ARCHETYPE: dict[str, str] = {
    "2021_british_grand_prix": "High-Speed",
    "2021_saudi_arabian_grand_prix": "Street",
    "2022_monaco_grand_prix": "Street",
    "2021_abu_dhabi_grand_prix": "Technical",
    "2022_japanese_grand_prix": "Technical",
    "2021_belgian_grand_prix": "High-Speed",
    **{f"{yr}_{slug}": arch for yr, slug, _, arch in OPENF1_CHRONO_ORDER},
}

TOP_TEAMS_KEYWORDS = ("RED BULL", "MERCEDES", "FERRARI", "MCLAREN")


def _parse_iso_ts(val: str | None) -> float | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _is_top_constructor(team_name: str) -> str:
    up = str(team_name or "").upper()
    return "Top-4 Constructors" if any(k in up for k in TOP_TEAMS_KEYWORDS) else "Midfield / Other"


def _build_neutralised_intervals(rc_rows: list[dict[str, Any]]) -> tuple[list[tuple[float, float]], bool, bool]:
    """Reconstruct [start_ts, end_ts] SC/VSC/RedFlag intervals causally from race_control rows."""
    events: list[tuple[float, dict[str, Any]]] = []
    for row in rc_rows:
        ts = _parse_iso_ts(row.get("date"))
        if ts is not None:
            events.append((ts, row))
    events.sort(key=lambda x: x[0])

    intervals: list[tuple[float, float]] = []
    active_start: float | None = None
    active_mode: str | None = None
    saw_red = False
    saw_sc_vsc = False

    for ts, row in events:
        cat = str(row.get("category") or "").upper()
        flag = str(row.get("flag") or "").upper()
        msg = str(row.get("message") or "").upper()

        is_deploy = (
            ("SAFETY CAR DEPLOYED" in msg and "IN THIS LAP" not in msg and "OVERTAKE" not in msg)
            or ("VIRTUAL SAFETY CAR DEPLOYED" in msg)
            or (flag == "RED" or "RED FLAG" in msg)
        )
        is_clear = (
            ("TRACK CLEAR" in msg and "SECTOR" not in msg)
            or ("VIRTUAL SAFETY CAR ENDING" in msg)
            or ("CHEQUERED FLAG" in msg)
            or (active_mode == "RED" and ("STANDING START" in msg or "ROLLING START" in msg) and "PROCEDURE" not in msg)
        )
        if flag == "RED" or "RED FLAG" in msg:
            saw_red = True
        if "SAFETY CAR DEPLOYED" in msg or "VIRTUAL SAFETY CAR DEPLOYED" in msg:
            saw_sc_vsc = True

        if is_deploy and active_start is None:
            active_start = ts
            active_mode = "RED" if (flag == "RED" or "RED FLAG" in msg) else "SC"
        elif is_deploy and active_start is not None and (flag == "RED" or "RED FLAG" in msg):
            active_mode = "RED"
        elif is_clear and active_start is not None:
            end_ts = ts + (2.0 if cat == "SAFETYCAR" and "ENDING" in msg else 0.0)
            intervals.append((active_start, end_ts))
            active_start = None
            active_mode = None

    if active_start is not None:
        intervals.append((active_start, float("inf")))
    return intervals, saw_sc_vsc or saw_red, saw_red


def load_openf1_causal_laps(cache_path: str | Path) -> dict[str, Any]:
    """Load an offline OpenF1 JSON race bundle into strictly causal CausalLapRecords."""
    bundle = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    year = int(bundle["year"])
    slug = str(bundle["name"])
    sess_id = f"{year}_{slug}"
    gp_display = next((disp for y, s, disp, _ in OPENF1_CHRONO_ORDER if y == year and s == slug), f"{year} {slug}")

    drivers_map = {
        int(d["driver_number"]): str(d.get("team_name") or "UNKNOWN")
        for d in bundle.get("drivers", [])
        if d.get("driver_number") is not None
    }
    stints_by_drv: dict[int, list[dict[str, Any]]] = {}
    for st in bundle.get("stints", []):
        dn = st.get("driver_number")
        if dn is not None:
            stints_by_drv.setdefault(int(dn), []).append(st)
    for lst in stints_by_drv.values():
        lst.sort(key=lambda s: int(s.get("stint_number") or 1))

    pit_in_laps: set[tuple[int, int]] = {
        (int(p["driver_number"]), int(p["lap_number"]))
        for p in bundle.get("pit", [])
        if p.get("driver_number") is not None and p.get("lap_number") is not None
    }

    rain_times: list[float] = []
    rain_flags: list[bool] = []
    for w in sorted(bundle.get("weather", []), key=lambda x: x.get("date") or ""):
        wt = _parse_iso_ts(w.get("date"))
        if wt is not None:
            rain_times.append(wt)
            rain_flags.append(bool((w.get("rainfall") or 0) > 0))

    neut_intervals, saw_sc_vsc, saw_red = _build_neutralised_intervals(bundle.get("race_control", []))

    raw_laps = bundle.get("laps", [])
    total_laps = max((int(l.get("lap_number") or 0) for l in raw_laps), default=0)

    # Precompute causal lap start times per lap number
    lap_starts_by_lap: dict[int, list[tuple[float, int]]] = {}
    parsed_laps: list[tuple[int, float, dict[str, Any]]] = []
    for row in raw_laps:
        ln = row.get("lap_number")
        dn = row.get("driver_number")
        dur = row.get("lap_duration")
        ds = _parse_iso_ts(row.get("date_start"))
        if ln is None or dn is None:
            continue
        ln_i = int(ln)
        dn_i = int(dn)
        if ds is not None:
            lap_starts_by_lap.setdefault(ln_i, []).append((ds, dn_i))
        if dur is None:
            continue
        try:
            dur_f = float(dur)
        except Exception:
            continue
        if not math.isfinite(dur_f) or dur_f <= 35.0 or dur_f >= 300.0:
            continue
        comp_ts = (ds + dur_f) if ds is not None else float(ln_i * 1000.0)
        parsed_laps.append((ln_i, comp_ts, row))

    for ln_i in lap_starts_by_lap:
        lap_starts_by_lap[ln_i].sort(key=lambda x: x[0])

    # Sort strictly in causal crossing order (LapNumber, completion_timestamp)
    parsed_laps.sort(key=lambda x: (x[0], x[1]))

    records: list[CausalLapRecord] = []
    last_neut_lap = 0

    for ln_i, comp_ts, row in parsed_laps:
        dn_i = int(row["driver_number"])
        dur_f = float(row["lap_duration"])
        ds = _parse_iso_ts(row.get("date_start"))

        # Stint & compound at current lap_number (causal: lap_start <= ln_i <= lap_end)
        stint_id = 1
        comp = "UNKNOWN"
        tyre_age = ln_i
        for st in stints_by_drv.get(dn_i, []):
            l_start = int(st.get("lap_start") or 1)
            l_end = int(st.get("lap_end") or 999) if st.get("lap_end") else 999
            if l_start <= ln_i <= l_end:
                stint_id = int(st.get("stint_number") or 1)
                comp = normalize_compound(st.get("compound"))
                age0 = int(st.get("tyre_age_at_start") or 0)
                tyre_age = max(1, age0 + (ln_i - l_start) + 1)
                break

        is_pit = bool(row.get("is_pit_out_lap")) or ((dn_i, ln_i) in pit_in_laps)

        neut = False
        if ds is not None:
            end_ts = ds + dur_f
            for iv_s, iv_e in neut_intervals:
                if ds <= iv_e and end_ts >= iv_s:
                    neut = True
                    break
        if neut:
            last_neut_lap = max(last_neut_lap, ln_i)
        post_restart = (not neut) and (last_neut_lap > 0) and (0 < (ln_i - last_neut_lap) <= 5)

        cur_rainfall = False
        if rain_times and ds is not None:
            r_idx = bisect_right(rain_times, ds + dur_f) - 1
            if r_idx >= 0:
                cur_rainfall = rain_flags[r_idx]
        is_wet = bool(cur_rainfall or comp in {"INTERMEDIATE", "WET"})

        # Causal position & interval from same-lap date_start stamps <= my_start
        pos: int | None = None
        interval_sec: float | None = None
        if ds is not None and ln_i in lap_starts_by_lap:
            starts = lap_starts_by_lap[ln_i]
            prior = [t for t, other_dn in starts if t < ds and other_dn != dn_i]
            pos = len(prior) + 1
            if pos > 1 and prior:
                interval_sec = round(max(0.0, ds - prior[-1]), 3)

        ca_status, _ = resolve_clean_air_status(position=pos, interval_sec=interval_sec, is_pit=is_pit)
        records.append(
            CausalLapRecord(
                session_id=sess_id,
                driver_number=dn_i,
                lap_number=ln_i,
                lap_sec=dur_f,
                stint_id=stint_id,
                compound=comp,
                tyre_age=tyre_age,
                position=pos,
                interval_sec=interval_sec,
                clean_air_status=ca_status,
                is_pit=is_pit,
                neutralised=neut,
                total_laps=total_laps,
                team_name=drivers_map.get(dn_i, "UNKNOWN"),
                is_wet=is_wet,
                post_restart_lap=post_restart,
            )
        )

    return {
        "session_id": sess_id,
        "year": year,
        "gp_name": gp_display,
        "total_laps": total_laps,
        "source": "OpenF1",
        "had_red_flag": saw_red,
        "had_sc_or_vsc": saw_sc_vsc,
        "had_wet_laps": any(r.is_wet for r in records),
        "records": records,
    }


def compute_residual_autocorrelation(points: list[LapPredictionPoint]) -> dict[str, float | int | None]:
    """Compute within-stint lag-1 residual & squared-error autocorrelation to quantify non-i.i.d. dependence."""
    by_stint: dict[tuple[str, int, int], list[tuple[int, float]]] = {}
    for p in points:
        if p.pred_sec is not None:
            by_stint.setdefault((p.session_id, p.driver_number, p.stint_id), []).append(
                (p.lap_number, p.actual_sec - p.pred_sec)
            )
    xs: list[float] = []
    ys: list[float] = []
    axs: list[float] = []
    ays: list[float] = []
    for lst in by_stint.values():
        lst.sort(key=lambda item: item[0])
        for (l1, e1), (l2, e2) in zip(lst, lst[1:]):
            if l2 - l1 <= 2:
                xs.append(e1)
                ys.append(e2)
                axs.append(abs(e1))
                ays.append(abs(e2))
    if len(xs) < 10:
        return {"n_pairs": len(xs), "lag1_signed_resid_acf": None, "lag1_abs_err_acf": None}

    def _corr(a: list[float], b: list[float]) -> float | None:
        ma = statistics.mean(a)
        mb = statistics.mean(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        da = math.sqrt(sum((x - ma) ** 2 for x in a))
        db = math.sqrt(sum((y - mb) ** 2 for y in b))
        return round(num / (da * db), 4) if da > 0 and db > 0 else None

    return {
        "n_pairs": len(xs),
        "n_stint_clusters": len(by_stint),
        "lag1_signed_resid_acf": _corr(xs, ys),
        "lag1_abs_err_acf": _corr(axs, ays),
    }


def cluster_bootstrap_metrics(
    points: list[LapPredictionPoint],
    *,
    n_boot: int = 2000,
    seed: int = 42,
    cluster_by: str = "stint",
) -> dict[str, Any]:
    """Compute MAE, RMSE, PI95 coverage and 95% block-bootstrap CIs over correlated clusters."""
    eval_pts = [p for p in points if p.pred_sec is not None]
    if not eval_pts:
        return {
            "n_target_laps": len(points),
            "n_predicted": 0,
            "n_clusters": 0,
            "mae_sec": None,
            "rmse_sec": None,
            "pi95_coverage": None,
            "mean_pi95_width_sec": None,
        }

    clusters: dict[Any, tuple[int, float, float, int, float]] = {}
    for p in eval_pts:
        cid = p.session_id if cluster_by == "session" else (p.session_id, p.driver_number, p.stint_id)
        err = p.actual_sec - p.pred_sec
        ae = abs(err)
        hit = 1 if (p.ci95_low_sec is not None and p.ci95_high_sec is not None and p.ci95_low_sec <= p.actual_sec <= p.ci95_high_sec) else 0
        width = (p.ci95_high_sec - p.ci95_low_sec) if (p.ci95_low_sec is not None and p.ci95_high_sec is not None) else 0.0
        n_c, sum_ae, sum_sq, sum_hit, sum_w = clusters.get(cid, (0, 0.0, 0.0, 0, 0.0))
        clusters[cid] = (n_c + 1, sum_ae + ae, sum_sq + err * err, sum_hit + hit, sum_w + width)

    cluster_list = list(clusters.values())
    tot_n = sum(c[0] for c in cluster_list)
    point_mae = sum(c[1] for c in cluster_list) / tot_n
    point_rmse = math.sqrt(sum(c[2] for c in cluster_list) / tot_n)
    point_cov = sum(c[3] for c in cluster_list) / tot_n
    point_w = sum(c[4] for c in cluster_list) / tot_n

    def _ci(vals: list[float]) -> list[float]:
        s = sorted(vals)
        lo_idx = max(0, int(0.025 * len(s)))
        hi_idx = min(len(s) - 1, int(0.975 * len(s)))
        return [round(s[lo_idx], 4), round(s[hi_idx], 4)]

    if len(cluster_list) < 2:
        return {
            "n_target_laps": len(points),
            "n_predicted": tot_n,
            "n_clusters": len(cluster_list),
            "coverage_fraction": round(tot_n / max(len(points), 1), 4),
            "mae_sec": round(point_mae, 4),
            "mae_ci95": None,
            "rmse_sec": round(point_rmse, 4),
            "rmse_ci95": None,
            "pi95_coverage": round(point_cov, 4),
            "pi95_coverage_ci95": None,
            "mean_pi95_width_sec": round(point_w, 4),
        }

    rng = random.Random(seed)
    k_clusters = len(cluster_list)
    boot_mae: list[float] = []
    boot_rmse: list[float] = []
    boot_cov: list[float] = []

    for _ in range(n_boot):
        bn = 0
        bae = 0.0
        bsq = 0.0
        bhit = 0
        for _idx in range(k_clusters):
            nc, sae, ssq, shit, _sw = cluster_list[rng.randrange(k_clusters)]
            bn += nc
            bae += sae
            bsq += ssq
            bhit += shit
        if bn > 0:
            boot_mae.append(bae / bn)
            boot_rmse.append(math.sqrt(bsq / bn))
            boot_cov.append(bhit / bn)

    return {
        "n_target_laps": len(points),
        "n_predicted": tot_n,
        "n_clusters": k_clusters,
        "coverage_fraction": round(tot_n / max(len(points), 1), 4),
        "mae_sec": round(point_mae, 4),
        "mae_ci95": _ci(boot_mae),
        "rmse_sec": round(point_rmse, 4),
        "rmse_ci95": _ci(boot_rmse),
        "pi95_coverage": round(point_cov, 4),
        "pi95_coverage_ci95": _ci(boot_cov),
        "mean_pi95_width_sec": round(point_w, 4),
        "autocorr": compute_residual_autocorrelation(eval_pts) if cluster_by == "stint" else None,
    }


def paired_common_support_comparison(
    pts_by_model: dict[str, list[LapPredictionPoint]],
    *,
    model_a: str = "revised_pulse",
    model_b: str = "existing_fuel_compensated",
    n_boot: int = 2000,
    seed: int = 42,
) -> dict[str, Any]:
    """Compare models on identical common-support laps & inspect any abstention subset."""
    def _key(p: LapPredictionPoint) -> tuple[str, int, int]:
        return (p.session_id, p.driver_number, p.lap_number)

    map_a = {_key(p): p for p in pts_by_model[model_a]}
    map_b = {_key(p): p for p in pts_by_model[model_b]}

    common_a: list[LapPredictionPoint] = []
    common_b: list[LapPredictionPoint] = []
    abstained_a_only: list[LapPredictionPoint] = []

    paired_clusters: dict[tuple[str, int, int], list[float]] = {}
    for k, pb in map_b.items():
        pa = map_a.get(k)
        if pb.pred_sec is not None and pa is not None and pa.pred_sec is not None:
            common_a.append(pa)
            common_b.append(pb)
            cid = (pa.session_id, pa.driver_number, pa.stint_id)
            paired_clusters.setdefault(cid, []).append(abs(pa.actual_sec - pa.pred_sec) - abs(pb.actual_sec - pb.pred_sec))
        elif pb.pred_sec is not None and (pa is None or pa.pred_sec is None):
            abstained_a_only.append(pb)

    rng = random.Random(seed)
    c_lists = list(paired_clusters.values())
    deltas: list[float] = []
    if len(c_lists) >= 2:
        for _ in range(n_boot):
            tot = 0.0
            cnt = 0
            for _ in range(len(c_lists)):
                row = c_lists[rng.randrange(len(c_lists))]
                tot += sum(row)
                cnt += len(row)
            if cnt > 0:
                deltas.append(tot / cnt)
    s_deltas = sorted(deltas)
    all_diffs = [d for row in c_lists for d in row]

    # 6-model strict common intersection
    model_names = list(pts_by_model.keys())
    valid_keys_per_model = [
        {_key(p) for p in pts_by_model[m] if p.pred_sec is not None}
        for m in model_names
    ]
    strict_common_keys = set.intersection(*valid_keys_per_model) if valid_keys_per_model else set()
    strict_6way: dict[str, Any] = {}
    for m in model_names:
        m_pts = [p for p in pts_by_model[m] if _key(p) in strict_common_keys]
        strict_6way[m] = cluster_bootstrap_metrics(m_pts, n_boot=n_boot, seed=seed)

    return {
        "pair": [model_a, model_b],
        "n_common": len(common_a),
        f"{model_a}_on_common": cluster_bootstrap_metrics(common_a, n_boot=n_boot, seed=seed),
        f"{model_b}_on_common": cluster_bootstrap_metrics(common_b, n_boot=n_boot, seed=seed),
        "paired_delta_mae_a_minus_b": round(statistics.mean(all_diffs), 4) if all_diffs else None,
        "paired_delta_mae_stint_ci95": (
            [round(s_deltas[int(0.025 * len(s_deltas))], 4), round(s_deltas[min(len(s_deltas) - 1, int(0.975 * len(s_deltas)))], 4)]
            if s_deltas else None
        ),
        "abstained_by_a_predicted_by_b_count": len(abstained_a_only),
        "b_performance_on_a_abstentions": cluster_bootstrap_metrics(abstained_a_only, n_boot=500, seed=seed),
        "strict_6way_common_support_count": len(strict_common_keys),
        "strict_6way_common_support": strict_6way,
    }


RACE_CALENDAR_ORDER: dict[str, int] = {
    "2021_british_grand_prix": 10,
    "2021_belgian_grand_prix": 12,
    "2021_saudi_arabian_grand_prix": 21,
    "2021_abu_dhabi_grand_prix": 22,
    "2022_monaco_grand_prix": 7,
    "2022_japanese_grand_prix": 18,
    "2023_austria": 9,
    "2023_great_britain": 10,
    "2023_netherlands": 13,
    "2023_singapore": 15,
    "2023_japan": 16,
    "2024_saudi_arabia": 2,
    "2024_monaco": 8,
    "2024_canada": 9,
    "2024_great_britain": 12,
    "2024_monza": 16,
    "2024_brazil": 21,
}


def run_extended_generalization_suite(
    fastf1_cache_dir: str | Path,
    openf1_cache_dir: str | Path,
    *,
    n_boot: int = 2000,
) -> dict[str, Any]:
    """Run full Phase J generalization & block-bootstrap suite across 2021-2024 FastF1 + OpenF1 races."""
    cal_data = [load_fastf1_causal_laps(fastf1_cache_dir, y, gp) for y, gp in CALIBRATION_RACES]
    hold_data = [load_fastf1_causal_laps(fastf1_cache_dir, y, gp) for y, gp in HOLDOUT_RACES]
    edge_data = [load_fastf1_causal_laps(fastf1_cache_dir, 2021, "Belgian Grand Prix")]
    openf1_data = [
        load_openf1_causal_laps(Path(openf1_cache_dir) / f"{y}_{slug}.json")
        for y, slug, _, _ in OPENF1_CHRONO_ORDER
        if (Path(openf1_cache_dir) / f"{y}_{slug}.json").exists()
    ]

    orig_main = cal_data + hold_data
    chrono_full = sorted(
        orig_main + openf1_data,
        key=lambda r: (int(r["year"]), RACE_CALENDAR_ORDER.get(r["session_id"], 99), r["session_id"]),
    )
    model_names = [
        "previous_lap",
        "rolling_5_median",
        "rolling_clean_air_median",
        "circuit_normalized_regression",
        "existing_fuel_compensated",
        "revised_pulse",
    ]

    # 1. Fixed 2021-2022 Calibration -> Unseen Holdout (2021-2022) & Completely Unseen External (2023-2024 OpenF1)
    cal_reg = _eval_regression_fit(cal_data)
    cal_eval = [evaluate_all_baselines_on_race(r, regression_params=cal_reg, return_points=True) for r in cal_data]
    hold_eval = [evaluate_all_baselines_on_race(r, regression_params=cal_reg, return_points=True) for r in hold_data]
    unseen_2324_eval = [evaluate_all_baselines_on_race(r, regression_params=cal_reg, return_points=True) for r in openf1_data]
    edge_eval = [evaluate_all_baselines_on_race(r, regression_params=cal_reg, return_points=True) for r in edge_data]

    def _pool_eval(evals: list[dict[str, Any]]) -> dict[str, list[LapPredictionPoint]]:
        pooled = {m: [] for m in model_names}
        for ev in evals:
            for m in model_names:
                pooled[m].extend(ev["points"][m])
        return pooled

    def _summarize_pool(pooled: dict[str, list[LapPredictionPoint]]) -> dict[str, Any]:
        return {m: cluster_bootstrap_metrics(pooled[m], n_boot=n_boot, seed=42) for m in model_names}

    # 2. Original 5-race LORO decomposition (explaining 1,560 obs & 93.91% PI95)
    loro5_eval: list[dict[str, Any]] = []
    for idx, test_r in enumerate(orig_main):
        tr = [r for j, r in enumerate(orig_main) if j != idx]
        params = _eval_regression_fit(tr)
        loro5_eval.append(evaluate_all_baselines_on_race(test_r, regression_params=params, return_points=True))
    loro5_pooled = _pool_eval(loro5_eval)

    # 3. Expanded 16-race LORO across 2021-2024
    loro16_eval: list[dict[str, Any]] = []
    for idx, test_r in enumerate(chrono_full):
        tr = [r for j, r in enumerate(chrono_full) if j != idx]
        params = _eval_regression_fit(tr)
        loro16_eval.append(evaluate_all_baselines_on_race(test_r, regression_params=params, return_points=True))
    loro16_pooled = _pool_eval(loro16_eval)

    # 4. Walk-Forward Chronological Validation (strict past -> next race across all 16 races; folds >= 1)
    wf_eval: list[dict[str, Any]] = []
    wf_per_race: list[dict[str, Any]] = []
    for idx in range(1, len(chrono_full)):
        tr = chrono_full[:idx]
        test_r = chrono_full[idx]
        params = _eval_regression_fit(tr)
        ev = evaluate_all_baselines_on_race(test_r, regression_params=params, return_points=True)
        wf_eval.append(ev)
        wf_per_race.append({
            "session_id": test_r["session_id"],
            "year": test_r["year"],
            "source": test_r.get("source"),
            "train_races_count": len(tr),
            "had_red_flag": bool(test_r.get("had_red_flag")),
            "had_sc_or_vsc": bool(test_r.get("had_sc_or_vsc")),
            "had_wet_laps": bool(test_r.get("had_wet_laps")),
            "models": ev["models"],
        })
    wf_pooled = _pool_eval(wf_eval)

    # 5. Stratifications on LORO-16 pooled predictions (plus unseen-2023-2024)
    race_meta_by_sid = {r["session_id"]: r for r in chrono_full}

    def _stratify(pooled: dict[str, list[LapPredictionPoint]], key_fn) -> dict[str, Any]:
        buckets: dict[str, dict[str, list[LapPredictionPoint]]] = {}
        for m in model_names:
            for p in pooled[m]:
                b_key = key_fn(p)
                if b_key is None:
                    continue
                buckets.setdefault(b_key, {mm: [] for mm in model_names})[m].append(p)
        return {
            b_key: {
                "models": {m: cluster_bootstrap_metrics(pts, n_boot=min(n_boot, 1000), seed=42) for m, pts in b_map.items()},
                "paired_revised_vs_existing": paired_common_support_comparison(b_map, n_boot=min(n_boot, 1000), seed=42),
            }
            for b_key, b_map in sorted(buckets.items())
        }

    stratifications = {
        "by_season": _stratify(loro16_pooled, lambda p: str(race_meta_by_sid[p.session_id]["year"])),
        "by_weather": _stratify(loro16_pooled, lambda p: "Wet / Rain" if p.is_wet else "Dry"),
        "by_compound": _stratify(loro16_pooled, lambda p: p.compound if p.compound != "UNKNOWN" else None),
        "by_interruption_regime": _stratify(
            loro16_pooled,
            lambda p: (
                "Red Flag + Restart Race"
                if race_meta_by_sid[p.session_id].get("had_red_flag")
                else ("SC/VSC Race" if race_meta_by_sid[p.session_id].get("had_sc_or_vsc") else "Clean Green Race")
            ),
        ),
        "by_post_restart_window": _stratify(loro16_pooled, lambda p: "Post-Restart (<=5 laps)" if p.post_restart_lap else "Steady Green"),
        "by_circuit_archetype": _stratify(loro16_pooled, lambda p: CIRCUIT_ARCHETYPE.get(p.session_id, "Mixed")),
        "by_team_tier": _stratify(loro16_pooled, lambda p: _is_top_constructor(p.team_name) if p.team_name != "UNKNOWN" else None),
    }

    return {
        "corpus_summary": {
            "total_races_loaded": len(chrono_full) + len(edge_data),
            "full_green_races": len(chrono_full),
            "edge_case_races": len(edge_data),
            "fastf1_races_2021_2022": len(orig_main) + len(edge_data),
            "openf1_races_2023_2024": len(openf1_data),
            "races": [
                {
                    "session_id": r["session_id"],
                    "year": r["year"],
                    "source": r.get("source"),
                    "total_laps": r["total_laps"],
                    "records": len(r["records"]),
                    "had_red_flag": bool(r.get("had_red_flag")),
                    "had_sc_or_vsc": bool(r.get("had_sc_or_vsc")),
                    "had_wet_laps": bool(r.get("had_wet_laps")),
                }
                for r in chrono_full + edge_data
            ],
        },
        "calibration_2021_2022_summary": _summarize_pool(_pool_eval(cal_eval)),
        "holdout_2021_2022_summary": _summarize_pool(_pool_eval(hold_eval)),
        "holdout_2021_2022_common_support": paired_common_support_comparison(_pool_eval(hold_eval), n_boot=n_boot),
        "unseen_external_2023_2024_summary": _summarize_pool(_pool_eval(unseen_2324_eval)),
        "unseen_external_2023_2024_common_support": paired_common_support_comparison(_pool_eval(unseen_2324_eval), n_boot=n_boot),
        "loro_5_race_investigation": {
            "stint_bootstrap_models": _summarize_pool(loro5_pooled),
            "session_bootstrap_revised_pulse": cluster_bootstrap_metrics(loro5_pooled["revised_pulse"], n_boot=n_boot, cluster_by="session"),
            "common_support_revised_vs_existing": paired_common_support_comparison(loro5_pooled, n_boot=n_boot),
        },
        "loro_16_race_summary": _summarize_pool(loro16_pooled),
        "loro_16_race_common_support": paired_common_support_comparison(loro16_pooled, n_boot=n_boot),
        "walk_forward_summary": _summarize_pool(wf_pooled),
        "walk_forward_common_support": paired_common_support_comparison(wf_pooled, n_boot=n_boot),
        "walk_forward_per_race": wf_per_race,
        "edge_case_belgium_2021": edge_eval[0]["models"],
        "stratifications": stratifications,
    }
