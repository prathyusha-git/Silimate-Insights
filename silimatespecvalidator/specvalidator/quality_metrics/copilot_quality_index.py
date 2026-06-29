"""
Copilot Quality Index (CQI) for Silimate.

A single composite health metric that rolls up all quality dimensions into one
trackable number (0.0 → 1.0). Product teams can plot this over time and set
alert thresholds (e.g., "alert if CQI drops below 0.55").

CQI formula:
  CQI = w_ppa  × ppa_pass_rate
      + w_cal  × (1 - brier_score)       ← calibration quality
      + w_lat  × latency_sla_rate         ← % sessions under SLA
      + w_acc  × adjusted_accept_rate     ← acceptance only where PPA passes
      + w_pred × (1 - pred_mape_clamped)  ← LLM prediction accuracy

Weights are tunable; defaults reflect an AI-engineer-sensible prior.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


# ── Tuneable weights ──────────────────────────────────────────────────────────
DEFAULT_WEIGHTS: Dict[str, float] = {
    "ppa_pass_rate":       0.30,  # fraction of suggestions that actually pass PPA
    "calibration":         0.20,  # how trustworthy confidence scores are
    "latency_sla":         0.15,  # fraction meeting the <3000ms SLA
    "adjusted_acceptance": 0.20,  # accept rate conditioned on PPA passing
    "pred_accuracy":       0.15,  # LLM internal PPA model accuracy
}

LATENCY_SLA_MS: int = 3000  # milliseconds


@dataclass
class CQIComponents:
    ppa_pass_rate: float
    calibration_score: float        # 1 - Brier score (or 0.5 baseline if unknown)
    latency_sla_rate: float
    adjusted_acceptance_rate: float
    pred_accuracy_score: float      # 1 - clamped MAPE
    weights: Dict[str, float]


@dataclass
class CQIResult:
    cqi: float                      # 0.0 → 1.0, higher is better
    components: CQIComponents
    grade: str                      # A / B / C / D / F
    alerts: List[str]               # actionable issues detected
    n_sessions: int


def compute_cqi(
    records: List[Any],
    brier_score: Optional[float] = None,
    overall_mape: Optional[float] = None,
    weights: Optional[Dict[str, float]] = None,
) -> CQIResult:
    """
    Compute CQI from a list of SuggestionRecord objects.

    Args:
        records:      list of SuggestionRecord
        brier_score:  pass in from CalibrationReport.brier_score (optional)
        overall_mape: pass in from PredictionErrorReport.overall_mape (optional)
        weights:      override DEFAULT_WEIGHTS if needed
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    # normalise weights to sum to 1.0
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}

    n = len(records)
    alerts: List[str] = []

    # ── PPA Pass Rate ─────────────────────────────────────────────────────────
    pass_count = sum(1 for r in records if r.fail_mode == "PASS")
    ppa_pass_rate = pass_count / n if n else 0.0
    if ppa_pass_rate < 0.20:
        alerts.append(
            f"CRITICAL: PPA pass rate {ppa_pass_rate:.1%} — copilot is generating "
            "failing suggestions 80%+ of the time. Prompt or model needs improvement."
        )
    elif ppa_pass_rate < 0.40:
        alerts.append(f"WARNING: PPA pass rate only {ppa_pass_rate:.1%} — below acceptable threshold (40%).")

    # ── Calibration Score ─────────────────────────────────────────────────────
    if brier_score is not None and not math.isnan(brier_score):
        # Brier ∈ [0, 1]; perfect = 0, random = 0.25. Map to 0→1 quality.
        # Score = max(0, 1 - brier / 0.25): normalise against random-guess baseline.
        calibration_score = max(0.0, 1.0 - brier_score / 0.25)
        if brier_score > 0.20:
            alerts.append(
                f"WARNING: Brier score {brier_score:.4f} — confidence scores are barely better "
                "than random. Recalibrate or retrain the confidence head."
            )
    else:
        calibration_score = 0.5  # neutral if we have no data
        alerts.append("INFO: Calibration data insufficient — using neutral baseline (0.5).")

    # ── Latency SLA Rate ─────────────────────────────────────────────────────
    lat_records = [r for r in records if r.latency_ms is not None]
    if lat_records:
        sla_pass = sum(1 for r in lat_records if r.latency_ms <= LATENCY_SLA_MS)
        latency_sla_rate = sla_pass / len(lat_records)
        if latency_sla_rate < 0.90:
            alerts.append(
                f"WARNING: Only {latency_sla_rate:.1%} of suggestions meet the "
                f"{LATENCY_SLA_MS}ms SLA. P95 latency likely exceeds user tolerance."
            )
    else:
        latency_sla_rate = 0.5
        alerts.append("INFO: No latency data available.")

    # ── Adjusted Acceptance Rate ───────────────────────────────────────────────
    # Acceptance rate conditioned on PPA passing — if the copilot makes a good
    # suggestion, does the user accept it? This isolates user satisfaction from PPA failures.
    ppa_pass_records = [r for r in records if r.fail_mode == "PASS"]
    if ppa_pass_records:
        adj_accept = sum(1 for r in ppa_pass_records if r.action == "accept") / len(ppa_pass_records)
        if adj_accept < 0.50:
            alerts.append(
                f"WARNING: Even when PPA passes, only {adj_accept:.1%} of suggestions are accepted. "
                "Users may have non-PPA concerns (RTL style, complexity, diff size)."
            )
    else:
        adj_accept = 0.0
        alerts.append("INFO: No PPA-passing records to compute adjusted acceptance rate.")

    # ── Prediction Accuracy Score ─────────────────────────────────────────────
    if overall_mape is not None and not math.isnan(overall_mape):
        # Clamp MAPE at 50% (anything worse than 50% MAPE is effectively useless)
        pred_accuracy_score = max(0.0, 1.0 - min(overall_mape, 0.5) / 0.5)
        if overall_mape > 0.20:
            alerts.append(
                f"WARNING: LLM PPA prediction MAPE = {overall_mape:.1%}. "
                "The model's internal PPA estimate is unreliable — calibrate the prediction head."
            )
    else:
        pred_accuracy_score = 0.5
        alerts.append("INFO: No prediction error data — using neutral baseline.")

    # ── Composite CQI ─────────────────────────────────────────────────────────
    cqi = (
        w["ppa_pass_rate"]       * ppa_pass_rate
        + w["calibration"]       * calibration_score
        + w["latency_sla"]       * latency_sla_rate
        + w["adjusted_acceptance"] * adj_accept
        + w["pred_accuracy"]     * pred_accuracy_score
    )
    cqi = round(min(1.0, max(0.0, cqi)), 4)

    grade = "A" if cqi >= 0.80 else "B" if cqi >= 0.65 else "C" if cqi >= 0.50 else "D" if cqi >= 0.35 else "F"

    return CQIResult(
        cqi=cqi,
        components=CQIComponents(
            ppa_pass_rate=round(ppa_pass_rate, 4),
            calibration_score=round(calibration_score, 4),
            latency_sla_rate=round(latency_sla_rate, 4),
            adjusted_acceptance_rate=round(adj_accept, 4),
            pred_accuracy_score=round(pred_accuracy_score, 4),
            weights=w,
        ),
        grade=grade,
        alerts=alerts,
        n_sessions=n,
    )


def format_cqi_report(result: CQIResult) -> str:
    c = result.components
    lines = [
        "Copilot Quality Index (CQI)",
        "=" * 50,
        f"  CQI Score:  {result.cqi:.4f}  (Grade: {result.grade})  [{result.n_sessions} sessions]",
        "",
        "  Component Breakdown:",
        f"  {'Component':<30} {'Score':>7}  {'Weight':>7}  {'Contrib':>8}",
        "  " + "-" * 58,
    ]
    components = [
        ("PPA Pass Rate",            c.ppa_pass_rate,            c.weights["ppa_pass_rate"]),
        ("Calibration (1-Brier)",    c.calibration_score,        c.weights["calibration"]),
        ("Latency SLA Rate",         c.latency_sla_rate,         c.weights["latency_sla"]),
        ("Adjusted Acceptance Rate", c.adjusted_acceptance_rate, c.weights["adjusted_acceptance"]),
        ("Pred. Accuracy (1-MAPE)",  c.pred_accuracy_score,      c.weights["pred_accuracy"]),
    ]
    for name, score, weight in components:
        contrib = score * weight
        lines.append(f"  {name:<30} {score:>7.3f}  {weight:>7.3f}  {contrib:>8.4f}")

    if result.alerts:
        lines += ["", "  Alerts:"]
        for a in result.alerts:
            lines.append(f"    ⚠  {a}")

    lines += [
        "",
        "  Interpretation: CQI ≥ 0.80 = production-ready, 0.65-0.79 = acceptable,",
        "  0.50-0.64 = needs work, < 0.50 = significant quality issues.",
    ]
    return "\n".join(lines)


# ── Per-design-type CQI ───────────────────────────────────────────────────────

@dataclass
class DesignTypeCQI:
    rtl_kind: str
    n: int
    cqi: float
    grade: str
    ppa_pass_rate: float
    mean_confidence: float
    acceptance_rate: float
    dominant_fail_mode: str


def compute_cqi_by_design_type(
    records: List[Any],
    weights: Optional[Dict[str, float]] = None,
) -> List[DesignTypeCQI]:
    """
    Compute a simplified CQI for each rtl_kind group.
    Returns list sorted by CQI ascending (worst first — most actionable).
    """
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for r in records:
        groups[r.rtl_kind or "unknown"].append(r)

    results: List[DesignTypeCQI] = []
    for kind, recs in groups.items():
        n = len(recs)
        ppa_pass_rate = sum(1 for r in recs if r.fail_mode == "PASS") / n
        mean_conf = (
            sum(r.confidence for r in recs if r.confidence is not None)
            / max(1, sum(1 for r in recs if r.confidence is not None))
        )
        accept_rate = sum(1 for r in recs if r.action == "accept") / n

        # Dominant fail mode
        fail_counts: dict = {}
        for r in recs:
            fail_counts[r.fail_mode] = fail_counts.get(r.fail_mode, 0) + 1
        dominant_fail = max(fail_counts, key=fail_counts.get)

        # Simplified CQI without calibration/pred components (not enough per-group data)
        lat_recs = [r.latency_ms for r in recs if r.latency_ms is not None]
        lat_sla = (
            sum(1 for l in lat_recs if l <= 3000) / len(lat_recs) if lat_recs else 0.5
        )
        pass_recs = [r for r in recs if r.fail_mode == "PASS"]
        adj_accept = (
            sum(1 for r in pass_recs if r.action == "accept") / len(pass_recs)
            if pass_recs else 0.0
        )

        # Use 3-component CQI for per-group (calibration & pred need more data)
        cqi = round(
            0.45 * ppa_pass_rate
            + 0.25 * lat_sla
            + 0.30 * adj_accept,
            4,
        )
        grade = (
            "A" if cqi >= 0.80 else
            "B" if cqi >= 0.65 else
            "C" if cqi >= 0.50 else
            "D" if cqi >= 0.35 else "F"
        )
        results.append(DesignTypeCQI(
            rtl_kind=kind,
            n=n,
            cqi=cqi,
            grade=grade,
            ppa_pass_rate=round(ppa_pass_rate, 4),
            mean_confidence=round(mean_conf, 4),
            acceptance_rate=round(accept_rate, 4),
            dominant_fail_mode=dominant_fail,
        ))

    return sorted(results, key=lambda x: x.cqi)


def format_design_type_cqi(results: List[DesignTypeCQI]) -> str:
    lines = [
        "Per-Design-Type CQI Breakdown",
        "=" * 65,
        f"  {'rtl_kind':<18} {'N':>4}  {'CQI':>6}  {'Grade':>5}  "
        f"{'PPA Pass':>9}  {'Adj Accept':>11}  {'Dominant Fail'}",
        "  " + "-" * 70,
    ]
    for d in results:
        lines.append(
            f"  {d.rtl_kind:<18} {d.n:>4}  {d.cqi:>6.4f}  {d.grade:>5}  "
            f"{d.ppa_pass_rate:>9.1%}  {d.acceptance_rate:>11.1%}  {d.dominant_fail_mode}"
        )
    if results:
        worst = results[0]
        best = results[-1]
        lines += [
            "",
            f"  Worst: {worst.rtl_kind} (CQI={worst.cqi:.4f}, grade {worst.grade})"
            f" — dominant fail: {worst.dominant_fail_mode}",
            f"  Best:  {best.rtl_kind} (CQI={best.cqi:.4f}, grade {best.grade})",
            "",
            "  Focus improvement on the lowest-CQI design types first.",
            "  Per-type CQI uses 3 components: PPA pass rate, latency SLA, adjusted acceptance.",
        ]
    return "\n".join(lines)
