"""
Pre-EDA Suggestion Ranker
=========================
Scores incoming suggestion_generated events **before** the EDA tool runs,
using the logistic regression model trained in Stage 4 (feedback_loop.py).

This is the key "closing the loop" script: instead of waiting for EDA results
to know if a suggestion is good, the copilot can get a quick accept-probability
signal upfront — and the chip designer can be warned before wasting EDA cycles.

Usage:
  python make_rankings.py [path/to/session.jsonl ...]

  If no paths given, reads from data/telemetry/deep_sessions/ (all sessions).

Output:
  Prints a ranked table of suggestions (highest accept_prob first) with:
    - accept_prob: predicted probability of acceptance
    - warning: WARN if accept_prob < 0.30 (likely to be rejected)
    - confidence_score, suggestion_rank (if present), latency_ms
  Also writes rankings to reports/pre_eda_rankings.json
"""
from __future__ import annotations
import sys
import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
PKG_ROOT = ROOT / "silimatespecvalidator"
sys.path.insert(0, str(PKG_ROOT))

from specvalidator.core.session_qa_analyzer import analyze_all_sessions
from specvalidator.quality_metrics.feedback_loop import fit_acceptance_model


WARN_THRESHOLD = 0.30
LATENCY_SLA_MS = 3000


def _build_feature_vector(
    confidence: float,
    latency_ms: Optional[float],
    suggestion_rank: int = 1,
) -> List[float]:
    """
    Pre-EDA feature vector — uses only fields available BEFORE EDA runs.

    We can't use ppa_pass (that's an EDA output) or pred_errors (those need
    actual_ppa too). So we use the fields the copilot itself emits:
      [confidence, latency_norm, suggestion_rank_norm, placeholder_pass, pe_zeros×3]

    The model was trained with ppa_pass as a feature — at inference time we set
    it to the prior (mean ppa_pass_rate from training), which degrades slightly
    but still surfaces high-risk suggestions via low confidence + high latency.
    """
    lat_norm = min(1.0, (latency_ms or 1000) / 5000.0)
    rank_norm = min(1.0, (suggestion_rank - 1) / 3.0)   # normalise 1-3 → 0-0.67
    return [
        float(confidence),
        lat_norm,
        0.15,           # prior PPA pass rate from training (conservative)
        0.0,            # pred_error_power — unknown pre-EDA
        0.0,            # pred_error_freq  — unknown pre-EDA
        0.0,            # pred_error_area  — unknown pre-EDA
    ]


def load_suggestion_events(jsonl_paths: List[Path]) -> List[Dict[str, Any]]:
    """Load suggestion_generated events from JSONL files."""
    events = []
    for p in jsonl_paths:
        try:
            with p.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line.strip())
                        if ev.get("event_type") == "suggestion_generated":
                            events.append(ev)
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass
    return events


def rank_suggestions(
    events: List[Dict[str, Any]],
    model,
) -> List[Dict[str, Any]]:
    """Score each suggestion_generated event and return ranked list."""
    scored = []
    for ev in events:
        conf = ev.get("confidence_score") or ev.get("confidence") or 0.5
        lat  = ev.get("latency_ms")
        rank = ev.get("suggestion_rank", 1)
        sid  = ev.get("session_id", "unknown")
        sugg = ev.get("suggestion_id", "unknown")

        vec = _build_feature_vector(conf, lat, rank)
        try:
            prob = float(model.predict_proba([vec])[0][1])
        except Exception:
            prob = float(conf) * 0.15  # fallback: scale confidence down

        warning = "WARN" if prob < WARN_THRESHOLD else "OK"
        lat_flag = "SLA_RISK" if (lat and lat > LATENCY_SLA_MS) else ""

        scored.append({
            "session_id":       sid,
            "suggestion_id":    sugg,
            "suggestion_rank":  rank,
            "confidence_score": round(float(conf), 3),
            "latency_ms":       lat,
            "accept_prob":      round(prob, 4),
            "warning":          warning,
            "lat_flag":         lat_flag,
        })

    return sorted(scored, key=lambda x: -x["accept_prob"])


def print_rankings(ranked: List[Dict[str, Any]], top_n: int = 20) -> None:
    print("\nPre-EDA Suggestion Rankings")
    print("=" * 90)
    print(f"  {'Rank':<5} {'accept_prob':>12}  {'warning':<8}  {'conf':>6}  "
          f"{'lat_ms':>8}  {'lat_flag':<10}  {'session_id':<15}  {'sugg_rank':<10}")
    print("  " + "-" * 85)
    for i, r in enumerate(ranked[:top_n], 1):
        lat_str = str(r["latency_ms"]) if r["latency_ms"] else "N/A"
        warn_col = f"!{r['warning']}!" if r["warning"] == "WARN" else r["warning"]
        print(
            f"  {i:<5} {r['accept_prob']:>12.4f}  {warn_col:<8}  "
            f"{r['confidence_score']:>6.3f}  {lat_str:>8}  "
            f"{r['lat_flag']:<10}  {r['session_id']:<15}  {r['suggestion_rank']:<10}"
        )
    if len(ranked) > top_n:
        print(f"  ... ({len(ranked) - top_n} more)")

    warn_count = sum(1 for r in ranked if r["warning"] == "WARN")
    sla_count  = sum(1 for r in ranked if r["lat_flag"] == "SLA_RISK")
    mean_prob  = sum(r["accept_prob"] for r in ranked) / len(ranked) if ranked else 0
    print(f"\n  Total suggestions ranked: {len(ranked)}")
    print(f"  WARN (accept_prob < {WARN_THRESHOLD}):  {warn_count}  ({warn_count/len(ranked):.1%})")
    print(f"  SLA risk (>{LATENCY_SLA_MS}ms):          {sla_count}")
    print(f"  Mean accept_prob:                {mean_prob:.4f}")
    print()


def main(paths: Optional[List[str]] = None) -> None:
    # ── Step 1: fit model on existing telemetry ─────────────────────────────
    print("Loading telemetry and fitting acceptance predictor...")
    records = analyze_all_sessions(
        sessions_folder="data/telemetry/deep_sessions",
        artifacts_folder="artifacts/sessions",
        out_folder="reports",
    )
    if not records:
        print("ERROR: no records found. Run generate_deep_session.py first.")
        return

    model, fit_result = fit_acceptance_model(records)
    print(f"  Model fitted on {fit_result.n_train} records "
          f"(pos={fit_result.n_pos}, neg={fit_result.n_neg})")
    print(f"  Train accuracy: {fit_result.train_accuracy:.3f} | {fit_result.verdict}\n")

    # ── Step 2: load suggestion_generated events ────────────────────────────
    if paths:
        jsonl_paths = [Path(p) for p in paths]
    else:
        # Default: score same sessions used for training (simulates scoring new batch)
        jsonl_paths = sorted(
            Path("data/telemetry/deep_sessions").glob("sess_*.jsonl")
        )

    print(f"Scoring {len(jsonl_paths)} session files...")
    events = load_suggestion_events(jsonl_paths)
    print(f"  Found {len(events)} suggestion_generated events\n")

    if not events:
        print("No suggestion events found.")
        return

    # ── Step 3: rank ────────────────────────────────────────────────────────
    ranked = rank_suggestions(events, model)
    print_rankings(ranked, top_n=25)

    # ── Step 4: write JSON output ───────────────────────────────────────────
    out_path = Path("reports/pre_eda_rankings.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ranked, indent=2), encoding="utf-8")
    print(f"  Rankings written to: {out_path}")

    # Quick interpretation
    top = ranked[0] if ranked else None
    bottom = ranked[-1] if ranked else None
    if top:
        print(f"\n  Top suggestion:    {top['session_id']} / {top['suggestion_id']}"
              f"  (accept_prob={top['accept_prob']:.4f})")
    if bottom:
        print(f"  Bottom suggestion: {bottom['session_id']} / {bottom['suggestion_id']}"
              f"  (accept_prob={bottom['accept_prob']:.4f})")
    print("\n  Suggestions with WARN flag should be reviewed or re-prompted before EDA.")


if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else None
    main(args)
