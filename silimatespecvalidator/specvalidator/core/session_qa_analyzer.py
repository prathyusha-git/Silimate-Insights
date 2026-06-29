from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import csv

from specvalidator.core.rtl_features import extract_features, diff_features


# =========================
# Data model
# =========================

@dataclass
class SuggestionRecord:
    session_id: str
    suggestion_id: str
    action: str
    action_reason: str
    confidence: Optional[float]
    latency_ms: Optional[int]

    # targets
    target_power: Optional[float]
    target_freq: Optional[float]
    target_area: Optional[float]

    # baseline (before)
    base_power: Optional[float]
    base_freq: Optional[float]
    base_area: Optional[float]

    # after (post-suggestion eval)
    actual_power: Optional[float]
    actual_freq: Optional[float]
    actual_area: Optional[float]

    # deltas (after - baseline)
    delta_power: Optional[float]
    delta_freq: Optional[float]
    delta_area: Optional[float]

    fail_mode: str
    action_alignment: str  # OK / RISKY_ACCEPT / SUSPICIOUS_REJECT / UNKNOWN

    rtl_before_ref: Optional[str]
    rtl_after_ref: Optional[str]
    diff_ref: Optional[str]

    root_cause_hypothesis: str

    # LLM-predicted PPA (from suggestion_generated event)
    pred_power: Optional[float] = None
    pred_freq: Optional[float] = None
    pred_area: Optional[float] = None

    # Prediction errors (pred - actual) — measures LLM internal model accuracy
    pred_error_power: Optional[float] = None
    pred_error_freq: Optional[float] = None
    pred_error_area: Optional[float] = None

    # Design context
    rtl_kind: Optional[str] = None

    # Debug fields (optional but SUPER helpful)
    rtl_before_abs: Optional[str] = None
    rtl_after_abs: Optional[str] = None
    rtl_before_exists: Optional[bool] = None
    rtl_after_exists: Optional[bool] = None


# =========================
# IO helpers
# =========================

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def _index_by(keys: List[str], events: List[Dict[str, Any]]) -> Dict[Tuple[Any, ...], List[Dict[str, Any]]]:
    idx: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for e in events:
        k = tuple(e.get(x) for x in keys)
        idx.setdefault(k, []).append(e)
    return idx


def _get_first(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return events[0] if events else None


# =========================
# Core extraction logic
# =========================

def _to_float(x: Any) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except Exception:
        return None


def _get_baseline(events: List[Dict[str, Any]]) -> Optional[Dict[str, Optional[float]]]:
    """
    Supports multiple schemas:
    - baseline_ppa: {baseline_power, baseline_freq, baseline_area, target_*}
    - ppa_snapshot: {target_*, actual_*} (use as baseline if earliest)
    """
    baseline = [e for e in events if e.get("event_type") in ("baseline_ppa",)]
    if baseline:
        b = baseline[0]
        base_power = b.get("baseline_power", b.get("actual_power"))
        base_freq = b.get("baseline_freq", b.get("actual_freq"))
        base_area = b.get("baseline_area", b.get("actual_area"))
        return {
            "base_power": _to_float(base_power),
            "base_freq": _to_float(base_freq),
            "base_area": _to_float(base_area),
            "target_power": _to_float(b.get("target_power")),
            "target_freq": _to_float(b.get("target_freq")),
            "target_area": _to_float(b.get("target_area")),
        }

    snaps = [e for e in events if e.get("event_type") in ("ppa_snapshot",)]
    if snaps:
        s = snaps[0]
        return {
            "base_power": _to_float(s.get("actual_power")),
            "base_freq": _to_float(s.get("actual_freq")),
            "base_area": _to_float(s.get("actual_area")),
            "target_power": _to_float(s.get("target_power")),
            "target_freq": _to_float(s.get("target_freq")),
            "target_area": _to_float(s.get("target_area")),
        }

    return None


def _get_eval_for_suggestion(events: List[Dict[str, Any]], suggestion_id: str) -> Optional[Dict[str, Any]]:
    ev = [
        e for e in events
        if e.get("event_type") in ("evaluation_result",) and e.get("suggestion_id") == suggestion_id
    ]
    if ev:
        return ev[-1]

    ev2 = [
        e for e in events
        if e.get("event_type") in ("ppa_snapshot",) and e.get("suggestion_id") == suggestion_id
    ]
    if ev2:
        return ev2[-1]

    return None


def _ppa_fail_mode(
    target_power: Optional[float],
    target_freq: Optional[float],
    target_area: Optional[float],
    actual_power: Optional[float],
    actual_freq: Optional[float],
    actual_area: Optional[float],
) -> str:
    if None in (target_power, target_freq, target_area, actual_power, actual_freq, actual_area):
        return "UNKNOWN"

    power_fail = actual_power > target_power
    freq_fail = actual_freq < target_freq
    area_fail = actual_area > target_area

    fails: List[str] = []
    if power_fail:
        fails.append("POWER")
    if freq_fail:
        fails.append("FREQ")
    if area_fail:
        fails.append("AREA")
    return "PASS" if not fails else "FAIL_" + "_".join(fails)


def _action_alignment(fail_mode: str, action: str) -> str:
    if fail_mode == "UNKNOWN":
        return "UNKNOWN"
    if fail_mode == "PASS" and action == "reject":
        return "SUSPICIOUS_REJECT"
    if fail_mode.startswith("FAIL_") and action == "accept":
        return "RISKY_ACCEPT"
    return "OK"


def _hypothesis_from_fail_and_features(fail_mode: str, feat_delta: Dict[str, Any]) -> str:
    if fail_mode in ("PASS", "UNKNOWN"):
        return "N/A"

    if "AREA" in fail_mode:
        if feat_delta.get("d_bitwidth_tokens", 0) > 0:
            return "AREA likely increased due to wider bitwidths."
        if feat_delta.get("d_mux_ternary", 0) > 0 or feat_delta.get("d_assign", 0) > 0:
            return "AREA likely increased due to added muxing/logic duplication."
        if feat_delta.get("d_always_ff", 0) > 0:
            return "AREA likely increased due to additional registers/pipeline stages."
        return "AREA failure observed; RTL deltas weak → needs deeper RTL-aware analysis."

    if "FREQ" in fail_mode:
        if feat_delta.get("d_max_ops_in_line", 0) > 0:
            return "FREQ likely regressed due to deeper combinational logic (more ops/line)."
        if feat_delta.get("d_always_ff", 0) < 0:
            return "FREQ may have regressed due to removed pipeline registers."
        return "FREQ failure observed; consider adding pipelining or reducing combo depth."

    if "POWER" in fail_mode:
        if feat_delta.get("d_op_xor", 0) > 0 or feat_delta.get("d_op_mul", 0) > 0:
            return "POWER likely increased due to switching-heavy operators (xor/mul)."
        if feat_delta.get("d_always_ff", 0) > 0:
            return "POWER may have increased due to extra sequential logic toggling."
        return "POWER failure observed; consider clock gating / enable conditions (future work)."

    return "Failure observed; needs refinement."


# =========================
# Path resolution (FIX)
# =========================

def _project_root_from_here() -> Path:
    """
    This file lives at: .../specvalidator/core/session_qa_analyzer.py
    parents:
      0 = session_qa_analyzer.py
      1 = core/
      2 = specvalidator/
      3 = silimatespecvalidator/
      4 = Silimate Insights/   <-- what we want
    """
    return Path(__file__).resolve().parents[4]


def _resolve_ref(ref: Optional[str], project_root: Path) -> Optional[Path]:
    if not ref:
        return None
    ref = str(ref).strip().replace("\\", "/")
    p = Path(ref)
    if p.is_absolute():
        return p
    return (project_root / p).resolve()


# =========================
# Main API
# =========================

def analyze_all_sessions(
    sessions_folder: str | Path = "data/telemetry/deep_sessions",
    artifacts_folder: str | Path = "artifacts/sessions",
    out_folder: str | Path = "reports",
) -> List[SuggestionRecord]:
    sessions_folder = Path(sessions_folder)
    artifacts_folder = Path(artifacts_folder)
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    records: List[SuggestionRecord] = []

    for jsonl in sorted(sessions_folder.glob("sess_*.jsonl")):
        events = _read_jsonl(jsonl)
        if not events:
            continue

        session_id = events[0].get("session_id") or jsonl.stem
        baseline = _get_baseline(events) or {}

        # Extract design context (rtl_kind for per-design-type analysis)
        ctx_events = [e for e in events if e.get("event_type") == "design_context"]
        rtl_kind = ctx_events[0].get("rtl_kind") if ctx_events else None

        # Support both names: suggestion_generated and suggestion_shown
        sug_events = [e for e in events if e.get("event_type") in ("suggestion_generated", "suggestion_shown")]
        act_events = [e for e in events if e.get("event_type") == "action_taken"]

        # Index actions by suggestion_id
        actions_by_id = {a.get("suggestion_id"): a for a in act_events if a.get("suggestion_id")}

        for s in sug_events:
            sugg_id = s.get("suggestion_id")
            if not sugg_id:
                continue

            act = actions_by_id.get(sugg_id, {})
            action = act.get("action", "unknown")
            action_reason = act.get("action_reason", "")

            ev = _get_eval_for_suggestion(events, sugg_id)

            # targets prefer evaluation_result, else baseline, else suggestion event
            target_power = (ev or {}).get("target_power", baseline.get("target_power", s.get("target_power")))
            target_freq = (ev or {}).get("target_freq", baseline.get("target_freq", s.get("target_freq")))
            target_area = (ev or {}).get("target_area", baseline.get("target_area", s.get("target_area")))

            # baseline actuals
            base_power = baseline.get("base_power")
            base_freq = baseline.get("base_freq")
            base_area = baseline.get("base_area")

            # after actuals
            actual_power = (ev or {}).get("actual_power", s.get("actual_power"))
            actual_freq = (ev or {}).get("actual_freq", s.get("actual_freq"))
            actual_area = (ev or {}).get("actual_area", s.get("actual_area"))

            # compute deltas if baseline exists
            def _f(x):
                try:
                    return float(x) if x is not None else None
                except Exception:
                    return None

            tp, tf, ta = _f(target_power), _f(target_freq), _f(target_area)
            bp, bf, ba = _f(base_power), _f(base_freq), _f(base_area)
            ap, af, aa = _f(actual_power), _f(actual_freq), _f(actual_area)

            dp = (ap - bp) if (ap is not None and bp is not None) else None
            df = (af - bf) if (af is not None and bf is not None) else None
            da = (aa - ba) if (aa is not None and ba is not None) else None

            fail_mode = _ppa_fail_mode(tp, tf, ta, ap, af, aa)
            alignment = _action_alignment(fail_mode, action)

            # Extract LLM-predicted PPA (from suggestion_generated)
            pred_power = _f(s.get("pred_power"))
            pred_freq = _f(s.get("pred_freq"))
            pred_area = _f(s.get("pred_area"))

            # Prediction errors: how wrong was the LLM's PPA estimate?
            pred_error_power = (pred_power - ap) if (pred_power is not None and ap is not None) else None
            pred_error_freq = (pred_freq - af) if (pred_freq is not None and af is not None) else None
            pred_error_area = (pred_area - aa) if (pred_area is not None and aa is not None) else None

            # SIMPLIFIED RTL PATH HANDLING - Just build the paths directly
            sess_dir = artifacts_folder / session_id
            rtl_before = str(sess_dir / "rtl_before.sv")
            rtl_after = str(sess_dir / "rtl_after_sugg_1.sv")
            diff_ref = str(sess_dir / "rtl_diff_sugg_1.patch")

            # Evidence via RTL features
            hypothesis = "N/A"
            if Path(rtl_before).exists() and Path(rtl_after).exists():
                f_before = extract_features(rtl_before)
                f_after = extract_features(rtl_after)
                fd = diff_features(f_before, f_after)
                hypothesis = _hypothesis_from_fail_and_features(fail_mode, fd)
            else:
                if fail_mode.startswith("FAIL_"):
                    hypothesis = "Failure observed but RTL artifacts missing → cannot attribute root cause"

            # Get confidence from the right field
            confidence = _f(s.get("confidence_score"))
            if confidence is None:
                confidence = _f(s.get("confidence"))

            # Create the SuggestionRecord
            record = SuggestionRecord(
                session_id=session_id,
                suggestion_id=sugg_id,
                action=action,
                action_reason=action_reason,
                confidence=confidence,
                latency_ms=s.get("latency_ms"),
                target_power=tp,
                target_freq=tf,
                target_area=ta,
                base_power=bp,
                base_freq=bf,
                base_area=ba,
                actual_power=ap,
                actual_freq=af,
                actual_area=aa,
                delta_power=dp,
                delta_freq=df,
                delta_area=da,
                fail_mode=fail_mode,
                action_alignment=alignment,
                rtl_before_ref=rtl_before,
                rtl_after_ref=rtl_after,
                diff_ref=diff_ref,
                root_cause_hypothesis=hypothesis,
                pred_power=pred_power,
                pred_freq=pred_freq,
                pred_area=pred_area,
                pred_error_power=pred_error_power,
                pred_error_freq=pred_error_freq,
                pred_error_area=pred_error_area,
                rtl_kind=rtl_kind,
            )
            
            records.append(record)

    # [Keep all the writing code the same - CSV, JSON, summary]

    # =========================
    # Write outputs
    # =========================

    # CSV
    csv_path = out_folder / "session_qa_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "suggestion_id", "action", "action_reason",
            "confidence", "latency_ms",
            "target_power", "target_freq", "target_area",
            "base_power", "base_freq", "base_area",
            "actual_power", "actual_freq", "actual_area",
            "delta_power", "delta_freq", "delta_area",
            "pred_power", "pred_freq", "pred_area",
            "pred_error_power", "pred_error_freq", "pred_error_area",
            "fail_mode", "action_alignment", "rtl_kind",
            "rtl_before_ref", "rtl_after_ref", "diff_ref",
            "root_cause_hypothesis",
            "rtl_before_abs", "rtl_after_abs",
            "rtl_before_exists", "rtl_after_exists",
        ])
        for r in records:
            writer.writerow([
                r.session_id, r.suggestion_id, r.action, r.action_reason,
                r.confidence, r.latency_ms,
                r.target_power, r.target_freq, r.target_area,
                r.base_power, r.base_freq, r.base_area,
                r.actual_power, r.actual_freq, r.actual_area,
                r.delta_power, r.delta_freq, r.delta_area,
                r.pred_power, r.pred_freq, r.pred_area,
                r.pred_error_power, r.pred_error_freq, r.pred_error_area,
                r.fail_mode, r.action_alignment, r.rtl_kind,
                r.rtl_before_ref, r.rtl_after_ref, r.diff_ref,
                r.root_cause_hypothesis,
                r.rtl_before_abs, r.rtl_after_abs,
                r.rtl_before_exists, r.rtl_after_exists,
            ])

    # JSON
    json_path = out_folder / "session_qa_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, indent=2)

    # Summary
    summary_path = out_folder / "session_qa_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("Session QA Analysis Summary\n")
        f.write("=" * 50 + "\n\n")
        #f.write(f"Project root: {project_root}\n")
        f.write(f"Telemetry folder: {sessions_folder}\n")
        f.write(f"Artifacts folder: {artifacts_folder}\n")
        f.write(f"Reports folder: {out_folder}\n\n")

        f.write(f"Total sessions analyzed: {len(set(r.session_id for r in records))}\n")
        f.write(f"Total suggestions analyzed:{len(records)}\n\n")

        # Action distribution
        f.write("Action Distribution:\n")
        action_counts: Dict[str, int] = {}
        for r in records:
            action_counts[r.action] = action_counts.get(r.action, 0) + 1
        for action, count in sorted(action_counts.items()):
            pct = (100 * count / len(records)) if records else 0.0
            f.write(f"  - {action}: {count} ({pct:.1f}%)\n")

        # Fail mode distribution
        f.write("\nFail Mode Distribution:\n")
        fail_counts: Dict[str, int] = {}
        for r in records:
            fail_counts[r.fail_mode] = fail_counts.get(r.fail_mode, 0) + 1
        for mode, count in sorted(fail_counts.items()):
            pct = (100 * count / len(records)) if records else 0.0
            f.write(f"  - {mode}: {count} ({pct:.1f}%)\n")

        # Action alignment
        f.write("\nAction Alignment:\n")
        align_counts: Dict[str, int] = {}
        for r in records:
            align_counts[r.action_alignment] = align_counts.get(r.action_alignment, 0) + 1
        for align, count in sorted(align_counts.items()):
            pct = (100 * count / len(records)) if records else 0.0
            f.write(f"  - {align}: {count} ({pct:.1f}%)\n")

        # RTL existence diagnostics
        missing_before = sum(1 for r in records if r.rtl_before_exists is False)
        missing_after = sum(1 for r in records if r.rtl_after_exists is False)
        f.write("\nRTL Artifact Diagnostics:\n")
        f.write(f"  - Missing rtl_before: {missing_before}\n")
        f.write(f"  - Missing rtl_after:  {missing_after}\n")

    print(f"Written {len(records)} records to: {csv_path}")
    print(f"Written JSON to: {json_path}")
    print(f"Written summary to: {summary_path}")

    return records
n summary to: {summary_path}")

    return records
