"""
PPA Prediction Error Analysis for Silimate Copilot.

The copilot emits predicted PPA (pred_power, pred_freq, pred_area) when generating
a suggestion. After EDA evaluation, we get actual PPA. The gap between prediction
and reality tells us how accurate the LLM's internal simulation model is.

Key metrics:
  MAE  = mean absolute error (same units as PPA)
  MAPE = mean absolute percentage error (scale-independent)
  Bias = mean signed error (positive = LLM overestimates, negative = underestimates)

Why this matters:
  High pred_error_power with low actual_power → LLM is pessimistic about power →
    might be rejecting good suggestions due to bad self-assessment.
  High pred_error_freq with negative bias → LLM underestimates timing →
    might be accepting suggestions that later fail timing closure.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import math


@dataclass
class DimensionError:
    dimension: str          # "power" | "freq" | "area"
    mae: float              # mean absolute error
    mape: float             # mean absolute percentage error (0-1 scale)
    bias: float             # mean signed error (pred - actual)
    max_abs_error: float
    n: int


@dataclass
class ByDesignType:
    rtl_kind: str
    n: int
    power_mape: Optional[float]
    freq_mape: Optional[float]
    area_mape: Optional[float]
    dominant_error_dim: str  # which dimension has highest MAPE


@dataclass
class PredictionErrorReport:
    power: DimensionError
    freq: DimensionError
    area: DimensionError
    by_design_type: List[ByDesignType]
    overall_mape: float         # average across all 3 dimensions
    worst_dimension: str        # power | freq | area
    verdict: str                # ACCURATE / MODERATE / INACCURATE


def _safe_mape(errors: List[float], actuals: List[float]) -> float:
    """MAPE, skipping actuals near zero to avoid division explosion."""
    pairs = [(abs(e), a) for e, a in zip(errors, actuals) if abs(a) > 1e-6]
    if not pairs:
        return float("nan")
    return sum(abs_err / abs(actual) for abs_err, actual in pairs) / len(pairs)


def analyze_prediction_errors(records: List[Any]) -> PredictionErrorReport:
    """
    Measure how accurately the copilot predicts PPA outcomes.
    Uses pred_error_* fields (pred - actual) from SuggestionRecord.
    """

    def _dim(err_attr: str, actual_attr: str) -> DimensionError:
        pairs = [
            (getattr(r, err_attr), getattr(r, actual_attr))
            for r in records
            if getattr(r, err_attr) is not None and getattr(r, actual_attr) is not None
        ]
        if not pairs:
            return DimensionError(
                dimension=err_attr.replace("pred_error_", ""),
                mae=float("nan"), mape=float("nan"),
                bias=float("nan"), max_abs_error=float("nan"), n=0,
            )
        errors = [p[0] for p in pairs]
        actuals = [p[1] for p in pairs]
        mae = sum(abs(e) for e in errors) / len(errors)
        bias = sum(errors) / len(errors)
        mape = _safe_mape(errors, actuals)
        max_abs = max(abs(e) for e in errors)
        return DimensionError(
            dimension=err_attr.replace("pred_error_", ""),
            mae=round(mae, 4),
            mape=round(mape, 4),
            bias=round(bias, 4),
            max_abs_error=round(max_abs, 4),
            n=len(pairs),
        )

    power_err = _dim("pred_error_power", "actual_power")
    freq_err = _dim("pred_error_freq", "actual_freq")
    area_err = _dim("pred_error_area", "actual_area")

    # Per-design-type breakdown
    kinds: Dict[str, List] = {}
    for r in records:
        k = r.rtl_kind or "unknown"
        kinds.setdefault(k, []).append(r)

    by_design: List[ByDesignType] = []
    for kind, recs in sorted(kinds.items()):
        def mape_for(err_attr, actual_attr):
            pairs = [
                (getattr(r, err_attr), getattr(r, actual_attr))
                for r in recs
                if getattr(r, err_attr) is not None and getattr(r, actual_attr) is not None
            ]
            if not pairs:
                return None
            return round(_safe_mape([p[0] for p in pairs], [p[1] for p in pairs]), 4)

        pm = mape_for("pred_error_power", "actual_power")
        fm = mape_for("pred_error_freq", "actual_freq")
        am = mape_for("pred_error_area", "actual_area")

        # Find dominant error dimension
        candidates = {"power": pm or 0, "freq": fm or 0, "area": am or 0}
        dominant = max(candidates, key=candidates.get)

        by_design.append(ByDesignType(
            rtl_kind=kind,
            n=len(recs),
            power_mape=pm,
            freq_mape=fm,
            area_mape=am,
            dominant_error_dim=dominant,
        ))

    # Overall MAPE: average of non-nan dimension MAPEs
    valid_mapes = [d.mape for d in [power_err, freq_err, area_err] if not math.isnan(d.mape)]
    overall_mape = round(sum(valid_mapes) / len(valid_mapes), 4) if valid_mapes else float("nan")

    # Worst dimension
    dim_mapes = {
        "power": power_err.mape if not math.isnan(power_err.mape) else -1,
        "freq": freq_err.mape if not math.isnan(freq_err.mape) else -1,
        "area": area_err.mape if not math.isnan(area_err.mape) else -1,
    }
    worst = max(dim_mapes, key=dim_mapes.get)

    # Verdict
    if math.isnan(overall_mape):
        verdict = "NO_DATA"
    elif overall_mape < 0.05:
        verdict = "ACCURATE"
    elif overall_mape < 0.15:
        verdict = "MODERATE"
    else:
        verdict = "INACCURATE"

    return PredictionErrorReport(
        power=power_err,
        freq=freq_err,
        area=area_err,
        by_design_type=by_design,
        overall_mape=overall_mape,
        worst_dimension=worst,
        verdict=verdict,
    )


def format_prediction_error_report(report: PredictionErrorReport) -> str:
    lines = [
        "PPA Prediction Error Analysis (LLM internal model accuracy)",
        "=" * 60,
        f"  Overall MAPE:    {report.overall_mape:.2%}  ({report.verdict})",
        f"  Worst dimension: {report.worst_dimension.upper()}",
        "",
        f"  {'Dim':<8} {'MAE':>10}  {'MAPE':>8}  {'Bias':>10}  {'Max|Err|':>10}  N",
        "  " + "-" * 58,
    ]
    for dim in [report.power, report.freq, report.area]:
        lines.append(
            f"  {dim.dimension.upper():<8} {dim.mae:>10.3f}  {dim.mape:>7.2%}  "
            f"{dim.bias:>10.3f}  {dim.max_abs_error:>10.3f}  {dim.n}"
        )

    if report.by_design_type:
        lines += [
            "",
            "  MAPE by Design Type:",
            f"  {'rtl_kind':<18} {'N':>3}  {'Power MAPE':>11}  {'Freq MAPE':>10}  {'Area MAPE':>10}  {'Worst':>8}",
            "  " + "-" * 70,
        ]
        for b in report.by_design_type:
            def fmt(v):
                return f"{v:.2%}" if v is not None else "   N/A"
            lines.append(
                f"  {b.rtl_kind:<18} {b.n:>3}  {fmt(b.power_mape):>11}  "
                f"{fmt(b.freq_mape):>10}  {fmt(b.area_mape):>10}  {b.dominant_error_dim.upper():>8}"
            )

    lines += [
        "",
        "  Bias interpretation: positive = LLM overestimates (optimistic), negative = underestimates.",
        "  High MAPE on FREQ → LLM's timing model is unreliable → freq-related accepts may be risky.",
    ]
    return "\n".join(lines)
