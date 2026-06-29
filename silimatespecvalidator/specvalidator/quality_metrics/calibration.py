"""
Confidence Calibration Analysis for Silimate Copilot.

Answers the core question: "When the copilot says confidence=0.85,
does the suggestion actually get accepted 85% of the time?"

Key metric: Brier Score (lower = better calibrated)
  BS = (1/N) * sum((confidence_i - outcome_i)^2)
  Perfect calibration = 0.0, random guessing = 0.25
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import math


@dataclass
class CalibrationBucket:
    lo: float
    hi: float
    n: int
    mean_confidence: float
    actual_acceptance_rate: float
    calibration_error: float  # |mean_confidence - actual_acceptance_rate|


@dataclass
class CalibrationReport:
    brier_score: float
    mean_calibration_error: float      # MCE = average |confidence - outcome|
    expected_calibration_error: float  # ECE = weighted avg |bucket_conf - bucket_acc|
    buckets: List[CalibrationBucket]
    overconfidence_rate: float  # fraction of records where confidence > actual outcome
    n_total: int
    verdict: str  # WELL_CALIBRATED / OVERCONFIDENT / UNDERCONFIDENT / INSUFFICIENT_DATA


def compute_calibration(records: List[Any]) -> CalibrationReport:
    """
    Compute confidence calibration metrics over SuggestionRecord list.

    A well-calibrated copilot: confidence=0.8 → ~80% of those suggestions get accepted.
    Overconfident copilot: confidence=0.8 but only 30% accepted → needs recalibration.
    """
    # Filter records with confidence and a clear binary outcome
    valid = [
        r for r in records
        if r.confidence is not None and r.action in ("accept", "reject", "modify")
    ]

    if len(valid) < 5:
        return CalibrationReport(
            brier_score=float("nan"),
            mean_calibration_error=float("nan"),
            expected_calibration_error=float("nan"),
            buckets=[],
            overconfidence_rate=float("nan"),
            n_total=len(valid),
            verdict="INSUFFICIENT_DATA",
        )

    # Binary outcome: accept=1, anything else=0
    outcomes = [1 if r.action == "accept" else 0 for r in valid]
    confidences = [r.confidence for r in valid]

    # ── Brier Score ──────────────────────────────────────────────────────────
    brier = sum((c - o) ** 2 for c, o in zip(confidences, outcomes)) / len(valid)

    # ── Mean Calibration Error ────────────────────────────────────────────────
    mce = sum(abs(c - o) for c, o in zip(confidences, outcomes)) / len(valid)

    # ── Overconfidence Rate ───────────────────────────────────────────────────
    overconf = sum(1 for c, o in zip(confidences, outcomes) if c > 0.5 and o == 0) / len(valid)

    # ── ECE: bucket into 5 equal-width bins ──────────────────────────────────
    bucket_edges = [0.0, 0.3, 0.5, 0.65, 0.8, 1.01]
    buckets: List[CalibrationBucket] = []

    for i in range(len(bucket_edges) - 1):
        lo, hi = bucket_edges[i], bucket_edges[i + 1]
        members = [(c, o) for c, o in zip(confidences, outcomes) if lo <= c < hi]
        if not members:
            continue
        mean_c = sum(c for c, _ in members) / len(members)
        mean_o = sum(o for _, o in members) / len(members)
        err = abs(mean_c - mean_o)
        buckets.append(CalibrationBucket(
            lo=lo, hi=hi,
            n=len(members),
            mean_confidence=round(mean_c, 4),
            actual_acceptance_rate=round(mean_o, 4),
            calibration_error=round(err, 4),
        ))

    ece = (
        sum(b.n * b.calibration_error for b in buckets) / len(valid)
        if buckets else float("nan")
    )

    # ── Verdict ───────────────────────────────────────────────────────────────
    if math.isnan(ece):
        verdict = "INSUFFICIENT_DATA"
    elif ece < 0.05:
        verdict = "WELL_CALIBRATED"
    elif overconf > 0.4:
        verdict = "OVERCONFIDENT"
    elif ece < 0.15:
        verdict = "SLIGHTLY_OVERCONFIDENT"
    else:
        verdict = "POORLY_CALIBRATED"

    return CalibrationReport(
        brier_score=round(brier, 4),
        mean_calibration_error=round(mce, 4),
        expected_calibration_error=round(ece, 4),
        buckets=buckets,
        overconfidence_rate=round(overconf, 4),
        n_total=len(valid),
        verdict=verdict,
    )


def format_calibration_report(report: CalibrationReport) -> str:
    lines = [
        "Confidence Calibration Analysis",
        "=" * 50,
        f"  Brier Score:                {report.brier_score:.4f}  (lower=better, random=0.25)",
        f"  Expected Calibration Error: {report.expected_calibration_error:.4f}  (lower=better)",
        f"  Mean Calibration Error:     {report.mean_calibration_error:.4f}",
        f"  Overconfidence Rate:        {report.overconfidence_rate:.1%}",
        f"  Verdict:                    {report.verdict}",
        f"  N (with confidence):        {report.n_total}",
        "",
        "  Calibration Buckets (confidence → actual acceptance):",
        f"  {'Bucket':<14} {'N':>4}  {'Avg Conf':>9}  {'Act. Accept':>12}  {'Error':>8}",
        "  " + "-" * 55,
    ]
    for b in report.buckets:
        label = f"[{b.lo:.2f}-{b.hi:.2f})"
        lines.append(
            f"  {label:<14} {b.n:>4}  {b.mean_confidence:>9.3f}  "
            f"{b.actual_acceptance_rate:>12.3f}  {b.calibration_error:>8.3f}"
        )
    lines.append("")
    lines.append(
        "  Interpretation: Brier < 0.10 → good. ECE < 0.05 → well-calibrated. "
        "High overconfidence → copilot over-promises."
    )
    return "\n".join(lines)
