"""
Confidence Recalibrator for Silimate Copilot.

Problem: the copilot emits confidence=0.87 but only 12.5% of those suggestions
get accepted. The raw confidence scores are poorly calibrated (Brier=0.48).

Solution: fit an isotonic regression that learns the monotone mapping from
raw confidence -> calibrated probability. After recalibration, confidence=0.87
gets remapped to ~0.12 — an honest estimate of actual acceptance probability.

This is standard production ML practice (Platt scaling / isotonic calibration).
It does NOT change the model; it post-processes its output scores.

Usage in production:
  1. Collect telemetry (done — 50+ sessions)
  2. Fit recalibrator on (raw_confidence, accept_outcome) pairs
  3. At inference time: calibrated_conf = recalibrator.predict(raw_conf)
  4. Surface calibrated_conf to users, not raw_conf
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Any, Dict
import math


@dataclass
class RecalibrationReport:
    n: int
    brier_before: float          # Brier score using raw confidence
    brier_after: float           # Brier score after isotonic recalibration
    brier_improvement: float     # brier_before - brier_after (positive = better)
    bucket_comparison: List[Dict]  # before vs after per confidence bucket
    verdict: str                 # IMPROVED / NO_IMPROVEMENT / INSUFFICIENT_DATA


def _brier(confs: List[float], outcomes: List[int]) -> float:
    return sum((c - o) ** 2 for c, o in zip(confs, outcomes)) / len(confs)


def fit_recalibrator(records: List[Any]):
    """
    Fit an isotonic regression recalibrator on SuggestionRecord list.
    Returns (fitted_calibrator, RecalibrationReport).

    The calibrator exposes .predict(X) where X is array of raw confidence scores.
    """
    try:
        from sklearn.isotonic import IsotonicRegression
        import numpy as np
    except ImportError:
        raise ImportError("scikit-learn required: pip install scikit-learn")

    valid = [
        (r.confidence, 1 if r.action == "accept" else 0)
        for r in records
        if r.confidence is not None and r.action in ("accept", "reject", "modify")
    ]

    if len(valid) < 10:
        return None, RecalibrationReport(
            n=len(valid), brier_before=float("nan"), brier_after=float("nan"),
            brier_improvement=float("nan"), bucket_comparison=[],
            verdict="INSUFFICIENT_DATA",
        )

    confs = [v[0] for v in valid]
    outcomes = [v[1] for v in valid]

    X = np.array(confs).reshape(-1, 1)
    y = np.array(outcomes, dtype=float)

    # Isotonic regression: learns monotone mapping conf -> P(accept)
    cal = IsotonicRegression(out_of_bounds="clip")
    cal.fit(confs, y)

    cal_confs = list(cal.predict(confs))

    brier_before = round(_brier(confs, outcomes), 4)
    brier_after = round(_brier(cal_confs, outcomes), 4)
    improvement = round(brier_before - brier_after, 4)

    # Bucket comparison
    bucket_edges = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.65), (0.65, 0.8), (0.8, 1.01)]
    bucket_comparison = []
    for lo, hi in bucket_edges:
        members = [(c, cal_c, o) for c, cal_c, o in zip(confs, cal_confs, outcomes)
                   if lo <= c < hi]
        if not members:
            continue
        raw_mean = sum(m[0] for m in members) / len(members)
        cal_mean = sum(m[1] for m in members) / len(members)
        act_rate = sum(m[2] for m in members) / len(members)
        bucket_comparison.append({
            "bucket": f"{lo:.2f}-{hi:.2f}",
            "n": len(members),
            "raw_confidence": round(raw_mean, 3),
            "calibrated_confidence": round(cal_mean, 3),
            "actual_acceptance": round(act_rate, 3),
            "raw_error": round(abs(raw_mean - act_rate), 3),
            "cal_error": round(abs(cal_mean - act_rate), 3),
        })

    verdict = "IMPROVED" if improvement > 0.01 else "MARGINAL_IMPROVEMENT" if improvement > 0 else "NO_IMPROVEMENT"

    return cal, RecalibrationReport(
        n=len(valid),
        brier_before=brier_before,
        brier_after=brier_after,
        brier_improvement=improvement,
        bucket_comparison=bucket_comparison,
        verdict=verdict,
    )


def format_recalibration_report(report: RecalibrationReport) -> str:
    lines = [
        "Confidence Recalibration (Isotonic Regression)",
        "=" * 58,
        f"  Status:            {report.verdict}",
        f"  N:                 {report.n}",
        f"  Brier BEFORE:      {report.brier_before:.4f}",
        f"  Brier AFTER:       {report.brier_after:.4f}",
        f"  Brier improvement: {report.brier_improvement:+.4f}  "
        f"({'better' if report.brier_improvement > 0 else 'no gain'})",
        "",
        f"  {'Bucket':<12} {'N':>3}  {'Raw Conf':>9}  {'Cal Conf':>9}  {'Actual':>8}  {'Raw Err':>8}  {'Cal Err':>8}",
        "  " + "-" * 68,
    ]
    for b in report.bucket_comparison:
        improvement_marker = "v" if b["cal_error"] < b["raw_error"] else "="
        lines.append(
            f"  {b['bucket']:<12} {b['n']:>3}  {b['raw_confidence']:>9.3f}  "
            f"{b['calibrated_confidence']:>9.3f}  {b['actual_acceptance']:>8.3f}  "
            f"{b['raw_error']:>8.3f}  {b['cal_error']:>8.3f} {improvement_marker}"
        )
    lines += [
        "",
        "  'v' = calibrated error is lower than raw error for that bucket.",
        "  In production: replace raw confidence with calibrated value before",
        "  surfacing to users. Re-fit recalibrator whenever new sessions arrive.",
    ]
    return "\n".join(lines)
