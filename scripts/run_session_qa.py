# scripts/run_session_qa.py
"""
Full QA pipeline runner — 8 stages with cached stage-1.

Stages:
  1. Analyze all telemetry sessions → CSV / JSON / summary  [cached if CSV fresh]
  2. Confidence calibration + Brier score
  3. LLM PPA prediction error analysis
  4. Train acceptance predictor on real data (feedback loop)
  5a. Copilot Quality Index (CQI) — composite
  5b. Per-design-type CQI breakdown
  6. Session clustering — find systematic failure patterns
  7. Confidence recalibration — isotonic regression remapping
  8. Pre-EDA rankings — score suggestions before EDA runs
"""
import sys
import math
import csv
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
PKG_ROOT = ROOT / "silimatespecvalidator"

sys.path.insert(0, str(PKG_ROOT))
sys.path.insert(0, str(SCRIPTS))


# ── Lightweight record loader (skip re-analysis if CSV is fresh) ──────────────

@dataclass
class CachedRecord:
    """Mirrors SuggestionRecord fields used by quality modules."""
    session_id: str
    suggestion_id: str
    action: Optional[str]
    action_reason: Optional[str]
    confidence: Optional[float]
    latency_ms: Optional[float]
    fail_mode: Optional[str]
    delta_power: Optional[float]
    delta_freq: Optional[float]
    delta_area: Optional[float]
    actual_power: Optional[float]
    actual_freq: Optional[float]
    actual_area: Optional[float]
    pred_power: Optional[float]
    pred_freq: Optional[float]
    pred_area: Optional[float]
    pred_error_power: Optional[float]
    pred_error_freq: Optional[float]
    pred_error_area: Optional[float]
    rtl_kind: Optional[str]
    action_alignment: Optional[str]


def _float(v):
    try:
        return float(v) if v not in ("", "None", None) else None
    except (ValueError, TypeError):
        return None


def load_records_from_csv(csv_path: Path):
    records = []
    with csv_path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(CachedRecord(
                session_id=row.get("session_id", ""),
                suggestion_id=row.get("suggestion_id", ""),
                action=row.get("action") or None,
                action_reason=row.get("action_reason") or None,
                confidence=_float(row.get("confidence")),
                latency_ms=_float(row.get("latency_ms")),
                fail_mode=row.get("fail_mode") or None,
                delta_power=_float(row.get("delta_power")),
                delta_freq=_float(row.get("delta_freq")),
                delta_area=_float(row.get("delta_area")),
                actual_power=_float(row.get("actual_power")),
                actual_freq=_float(row.get("actual_freq")),
                actual_area=_float(row.get("actual_area")),
                pred_power=_float(row.get("pred_power")),
                pred_freq=_float(row.get("pred_freq")),
                pred_area=_float(row.get("pred_area")),
                pred_error_power=_float(row.get("pred_error_power")),
                pred_error_freq=_float(row.get("pred_error_freq")),
                pred_error_area=_float(row.get("pred_error_area")),
                rtl_kind=row.get("rtl_kind") or None,
                action_alignment=row.get("action_alignment") or None,
            ))
    return records


def _csv_is_fresh(csv_path: Path, sessions_dir: Path) -> bool:
    """True if CSV exists and is newer than the newest session file."""
    if not csv_path.exists():
        return False
    csv_mtime = csv_path.stat().st_mtime
    session_files = list(sessions_dir.glob("sess_*.jsonl"))
    if not session_files:
        return False
    newest_session = max(f.stat().st_mtime for f in session_files)
    return csv_mtime >= newest_session


def run_pipeline():
    print("\n" + "=" * 65)
    print("  SILIMATE COPILOT QA PIPELINE")
    print("=" * 65 + "\n")

    csv_path = Path("reports/session_qa_results.csv")
    sessions_dir = Path("data/telemetry/deep_sessions")

    # Stage 1: Core session analysis (cached)
    if _csv_is_fresh(csv_path, sessions_dir):
        print("Stage 1 / 8 - Loading cached analysis results from CSV...")
        records = load_records_from_csv(csv_path)
        print(f"  -> {len(records)} records loaded from cache")
    else:
        print("Stage 1 / 8 - Analyzing telemetry sessions...")
        from specvalidator.core.session_qa_analyzer import analyze_all_sessions
        records = analyze_all_sessions(
            sessions_folder="data/telemetry/deep_sessions",
            artifacts_folder="artifacts/sessions",
            out_folder="reports",
        )
        print(f"  -> {len(records)} suggestion records extracted")
    print()

    # Stage 2: Confidence calibration
    from specvalidator.quality_metrics.calibration import (
        compute_calibration, format_calibration_report,
    )
    print("Stage 2 / 8 - Confidence calibration (Brier score)...")
    cal_report = compute_calibration(records)
    cal_text = format_calibration_report(cal_report)
    print(cal_text)

    # Stage 3: LLM PPA prediction error
    from specvalidator.quality_metrics.prediction_error_analyzer import (
        analyze_prediction_errors, format_prediction_error_report,
    )
    print("\nStage 3 / 8 - LLM PPA prediction error analysis...")
    pred_report = analyze_prediction_errors(records)
    pred_text = format_prediction_error_report(pred_report)
    print(pred_text)

    # Stage 4: Train acceptance predictor
    from specvalidator.quality_metrics.feedback_loop import (
        fit_acceptance_model, format_fit_report,
    )
    print("\nStage 4 / 8 - Training acceptance predictor on real telemetry...")
    model, fit_result = fit_acceptance_model(records)
    fit_text = format_fit_report(fit_result)
    print(fit_text)

    # Stage 5a: Overall CQI
    from specvalidator.quality_metrics.copilot_quality_index import (
        compute_cqi, format_cqi_report,
        compute_cqi_by_design_type, format_design_type_cqi,
    )
    print("\nStage 5 / 8 - Computing Copilot Quality Index (CQI)...")
    brier = cal_report.brier_score if not math.isnan(cal_report.brier_score) else None
    mape = pred_report.overall_mape if not math.isnan(pred_report.overall_mape) else None
    cqi_result = compute_cqi(records, brier_score=brier, overall_mape=mape)
    cqi_text = format_cqi_report(cqi_result)
    print(cqi_text)

    # Stage 5b: Per-design-type CQI
    print()
    design_cqi = compute_cqi_by_design_type(records)
    design_cqi_text = format_design_type_cqi(design_cqi)
    print(design_cqi_text)

    # Stage 6: Session clustering
    from specvalidator.core.session_clustering import (
        cluster_sessions, format_clustering_report,
    )
    print("\nStage 6 / 8 - Clustering sessions to find systematic patterns...")
    cluster_result = cluster_sessions(records, n_clusters=4)
    cluster_text = format_clustering_report(cluster_result)
    print(cluster_text)

    # Stage 7: Confidence recalibration
    from specvalidator.quality_metrics.recalibrator import (
        fit_recalibrator, format_recalibration_report,
    )
    print("\nStage 7 / 8 - Fitting isotonic recalibrator...")
    calibrator, recal_report = fit_recalibrator(records)
    recal_text = format_recalibration_report(recal_report)
    print(recal_text)

    # Stage 8: Pre-EDA suggestion rankings
    from make_rankings import rank_suggestions, load_suggestion_events, print_rankings
    print("\nStage 8 / 8 - Generating pre-EDA suggestion rankings...")
    jsonl_paths = sorted(sessions_dir.glob("sess_*.jsonl"))
    events = load_suggestion_events(jsonl_paths)
    ranked = rank_suggestions(events, model)
    print_rankings(ranked, top_n=10)
    out_path = Path("reports/pre_eda_rankings.json")
    out_path.write_text(json.dumps(ranked, indent=2), encoding="utf-8")
    print(f"  Full rankings -> {out_path}")

    # Write extended summary
    extended_path = Path("reports/extended_summary.txt")
    extended_path.parent.mkdir(parents=True, exist_ok=True)
    with open(extended_path, "w", encoding="utf-8") as f:
        f.write("SILIMATE COPILOT - EXTENDED QA REPORT\n")
        f.write("=" * 65 + "\n\n")
        f.write(cal_text + "\n\n")
        f.write(pred_text + "\n\n")
        f.write(fit_text + "\n\n")
        f.write(cqi_text + "\n\n")
        f.write(design_cqi_text + "\n\n")
        f.write(cluster_text + "\n\n")
        f.write(recal_text + "\n")
    print(f"\n  Extended report: {extended_path}")

    print("\n" + "=" * 65)
    print(f"  CQI: {cqi_result.cqi:.4f}  (Grade: {cqi_result.grade})")
    print(f"  Calibration verdict:       {cal_report.verdict}")
    print(f"  Prediction error verdict:  {pred_report.verdict}")
    print(f"  Recalibration:             {recal_report.verdict}  "
          f"(Brier {recal_report.brier_before:.4f} → {recal_report.brier_after:.4f})")
    print(f"  Clustering:                {cluster_result.verdict}  "
          f"({cluster_result.n_clusters} clusters)")
    if design_cqi:
        worst = design_cqi[0]
        print(f"  Weakest design type:       {worst.rtl_kind}  (CQI={worst.cqi:.4f}, {worst.grade})")
    print(f"  Pre-EDA rankings:          {len(ranked)} suggestions scored")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_pipeline()
