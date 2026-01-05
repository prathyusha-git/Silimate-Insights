from __future__ import annotations
from pathlib import Path
import json

from specvalidator.core.telemetry_analyzer import load_session_jsonl
from specvalidator.core.ppa_validator import check_ppa


def main():
    folder = Path("data/telemetry/deep_sessions")
    files = sorted(folder.glob("sess_*.jsonl"))
    if not files:
        raise SystemExit(f"No sess_*.jsonl found in {folder}")

    jsonl_file = files[0]  # pick first session for now
    sess = load_session_jsonl(jsonl_file)

    print("\nSESSION:", sess.session_id)
    # Find one suggestion generated + evaluation + action
    gen = sess.by_type("suggestion_generated")
    evs = sess.by_type("evaluation_result")
    acts = sess.by_type("action_taken")

    if not gen:
        print("No suggestion_generated events found.")
        return

    g = gen[0]
    sugg_id = g.get("suggestion_id")
    print("Suggestion:", sugg_id)
    print("Confidence:", g.get("confidence_score"), "Latency(ms):", g.get("latency_ms"))

    # match evaluation/action by suggestion_id
    e = next((x for x in evs if x.get("suggestion_id") == sugg_id), None)
    a = next((x for x in acts if x.get("suggestion_id") == sugg_id), None)

    if a:
        print("Action:", a.get("action"), "| reason:", a.get("action_reason"))

    if e and all(k in e for k in ["target_power","target_freq","target_area","actual_power","actual_freq","actual_area"]):
        target = {"target_power": e["target_power"], "target_freq": e["target_freq"], "target_area": e["target_area"]}
        actual = {"actual_power": e["actual_power"], "actual_freq": e["actual_freq"], "actual_area": e["actual_area"]}
        flags = check_ppa(target, actual)
        print("PPA:", flags.label)
        print("Targets:", target)
        print("Actual :", actual)
    else:
        print("No usable evaluation_result for this suggestion.")

    # show artifact paths (so you can open RTL)
    print("RTL before:", g.get("rtl_before_ref"))
    print("RTL after :", g.get("rtl_after_ref"))
    print("Diff     :", g.get("diff_ref"))


if __name__ == "__main__":
    main()
