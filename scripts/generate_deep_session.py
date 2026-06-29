"""
Synthetic telemetry generator — v2.
Changes vs v1:
  - 500 sessions (was 50) for credible ML training data
  - Per-design-type PPA targets (adder4 has tighter area budget, small_fsm tighter power)
  - 1-3 suggestions per session (was always 1) — tests ranking logic
  - suggestion_rank field on each suggestion
  - Wider confidence range (0.35-0.95) for better calibration coverage
  - action can now include 'rollback' (~5%) in addition to accept/reject/modify
"""
from __future__ import annotations
from pathlib import Path
import json
import uuid
from datetime import datetime, timezone
import random
import difflib
import hashlib


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def write_jsonl(path: Path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_diff(a: str, b: str) -> str:
    diff = difflib.unified_diff(
        a.splitlines(keepends=True),
        b.splitlines(keepends=True),
        fromfile="rtl_before.sv",
        tofile="rtl_after.sv",
    )
    return "".join(diff)


# ---- RTL templates ----

def rtl_template(kind: str, top_name: str) -> str:
    if kind == "logic_combo_1":
        return f"module {top_name}(input logic a,b,c, output logic y);\n  assign y = (a & b) | c;\nendmodule\n"
    if kind == "logic_combo_2":
        return f"module {top_name}(input logic a,b,c, output logic y);\n  assign y = (a | b) & (~c);\nendmodule\n"
    if kind == "logic_combo_3":
        return f"module {top_name}(input logic a,b,c, output logic y);\n  assign y = (a ^ b) ^ c;\nendmodule\n"
    if kind == "mux":
        return f"module {top_name}(input logic sel, d0, d1, output logic y);\n  assign y = sel ? d1 : d0;\nendmodule\n"
    if kind == "adder4":
        return f"module {top_name}(input logic [3:0] a,b, output logic [4:0] y);\n  assign y = a + b;\nendmodule\n"
    if kind == "small_fsm":
        return (
            f"module {top_name}(input logic clk, rst_n, in, output logic out);\n"
            f"  typedef enum logic [1:0] {{S0, S1, S2, S3}} state_t;\n"
            f"  state_t s, ns;\n"
            f"  always_ff @(posedge clk or negedge rst_n) begin\n"
            f"    if (!rst_n) s <= S0;\n    else s <= ns;\n  end\n"
            f"  always_comb begin\n    ns = s; out = 1'b0;\n"
            f"    unique case (s)\n"
            f"      S0: ns = in ? S1 : S0;\n"
            f"      S1: ns = in ? S2 : S0;\n"
            f"      S2: begin ns = in ? S3 : S0; out = 1'b1; end\n"
            f"      S3: ns = in ? S3 : S0;\n"
            f"    endcase\n  end\nendmodule\n"
        )
    if kind == "pipeline_add":
        return (
            f"module {top_name}(input logic clk, input logic [7:0] a, b, output logic [8:0] y);\n"
            f"  logic [7:0] a_r, b_r;\n"
            f"  always_ff @(posedge clk) begin a_r <= a; b_r <= b; end\n"
            f"  assign y = a_r + b_r;\nendmodule\n"
        )
    if kind == "shifter":
        return (
            f"module {top_name}(input logic [7:0] data, input logic [2:0] shamt, output logic [7:0] y);\n"
            f"  assign y = data << shamt;\nendmodule\n"
        )
    raise ValueError(f"Unknown rtl kind: {kind}")


def rewrite_style(kind: str, top_name: str, variant: int = 0) -> str:
    """Multiple rewrite variants per kind for multi-suggestion sessions."""
    if kind == "logic_combo_1":
        rewrites = [
            f"module {top_name}(input logic a,b,c, output logic y);\n  logic t;\n  assign t = a & b;\n  assign y = t | c;\nendmodule\n",
            f"module {top_name}(input logic a,b,c, output logic y);\n  assign y = (~a & c) | (a & b & c) | (a & b & ~c) | (~a & b & c);\nendmodule\n",
        ]
    elif kind == "logic_combo_2":
        rewrites = [
            f"module {top_name}(input logic a,b,c, output logic y);\n  logic t;\n  assign t = a | b;\n  assign y = t & ~c;\nendmodule\n",
            f"module {top_name}(input logic a,b,c, output logic y);\n  assign y = (a & ~c) | (b & ~c);\nendmodule\n",
        ]
    elif kind == "logic_combo_3":
        rewrites = [
            f"module {top_name}(input logic a,b,c, output logic y);\n  logic t;\n  assign t = a ^ b;\n  assign y = t ^ c;\nendmodule\n",
            f"module {top_name}(input logic a,b,c, output logic y);\n  assign y = (a & ~b & ~c) | (~a & b & ~c) | (~a & ~b & c) | (a & b & c);\nendmodule\n",
        ]
    elif kind == "mux":
        rewrites = [
            f"module {top_name}(input logic sel, d0, d1, output logic y);\n  assign y = (~sel & d0) | (sel & d1);\nendmodule\n",
            f"module {top_name}(input logic sel, d0, d1, output logic y);\n  always_comb\n    if (sel) y = d1;\n    else y = d0;\nendmodule\n",
        ]
    elif kind == "adder4":
        rewrites = [
            f"module {top_name}(input logic [3:0] a,b, output logic [4:0] y);\n  logic [4:0] aa, bb;\n  assign aa = {{1'b0,a}};\n  assign bb = {{1'b0,b}};\n  assign y = aa + bb;\nendmodule\n",
            f"module {top_name}(input logic [3:0] a,b, output logic [4:0] y);\n  logic carry;\n  logic [3:0] s;\n  assign {{carry, s}} = a + b;\n  assign y = {{carry, s}};\nendmodule\n",
        ]
    elif kind == "small_fsm":
        rewrites = [
            (
                f"module {top_name}(input logic clk, rst_n, in, output logic out);\n"
                f"  typedef enum logic [1:0] {{S0, S1, S2, S3}} state_t;\n"
                f"  state_t s, ns;\n"
                f"  always_ff @(posedge clk or negedge rst_n) begin\n"
                f"    if (!rst_n) s <= S0;\n    else s <= ns;\n  end\n"
                f"  always_comb begin\n    ns = s; out = 1'b0;\n"
                f"    unique case (s)\n"
                f"      S0: begin if (in) ns = S1; else ns = S0; end\n"
                f"      S1: begin if (in) ns = S2; else ns = S0; end\n"
                f"      S2: begin out = 1'b1; if (in) ns = S3; else ns = S0; end\n"
                f"      default: begin if (in) ns = S3; else ns = S0; end\n"
                f"    endcase\n  end\nendmodule\n"
            ),
        ]
    elif kind == "pipeline_add":
        rewrites = [
            (
                f"module {top_name}(input logic clk, input logic [7:0] a, b, output logic [8:0] y);\n"
                f"  logic [8:0] sum;\n"
                f"  assign sum = {{1'b0,a}} + {{1'b0,b}};\n"
                f"  always_ff @(posedge clk) y <= sum;\nendmodule\n"
            ),
        ]
    elif kind == "shifter":
        rewrites = [
            f"module {top_name}(input logic [7:0] data, input logic [2:0] shamt, output logic [7:0] y);\n  always_comb\n    y = data << shamt;\nendmodule\n",
        ]
    else:
        rewrites = [f"module {top_name}(); endmodule\n"]

    return rewrites[variant % len(rewrites)]


# Per-design-type PPA targets — more realistic than universal targets
DESIGN_TARGETS = {
    "logic_combo_1": {"target_power": 400,  "target_freq": 3000, "target_area": 5},
    "logic_combo_2": {"target_power": 450,  "target_freq": 2800, "target_area": 5},
    "logic_combo_3": {"target_power": 500,  "target_freq": 2600, "target_area": 6},
    "mux":           {"target_power": 300,  "target_freq": 3200, "target_area": 3},
    "adder4":        {"target_power": 750,  "target_freq": 2400, "target_area": 8},
    "small_fsm":     {"target_power": 650,  "target_freq": 2000, "target_area": 10},
    "pipeline_add":  {"target_power": 900,  "target_freq": 2200, "target_area": 12},
    "shifter":       {"target_power": 350,  "target_freq": 3500, "target_area": 4},
}

DESIGN_BASELINES = {
    "logic_combo_1": (300, 700,  3000, 3500, 3, 7),
    "logic_combo_2": (350, 750,  2700, 3200, 3, 7),
    "logic_combo_3": (380, 820,  2500, 3100, 4, 8),
    "mux":           (200, 500,  3000, 3800, 2, 5),
    "adder4":        (600, 980,  1800, 2500, 7, 14),
    "small_fsm":     (500, 900,  1500, 2400, 8, 14),
    "pipeline_add":  (700, 1100, 1800, 2600, 9, 16),
    "shifter":       (250, 600,  3200, 4000, 3, 6),
}


def synth_ppa(baseline_power, baseline_freq, baseline_area, targets, rng, suggestion_rank=1):
    """Later suggestions in a session are slightly better (simulating iterative improvement)."""
    quality_boost = 0.97 ** (suggestion_rank - 1)  # each subsequent suggestion slightly better
    pred = {
        "pred_power": round(baseline_power * rng.uniform(0.82, 1.05) * quality_boost, 2),
        "pred_freq":  round(baseline_freq  * rng.uniform(0.93, 1.14) / quality_boost, 2),
        "pred_area":  round(baseline_area  * rng.uniform(0.85, 1.08) * quality_boost, 2),
    }
    actual = {
        "actual_power": round(baseline_power * rng.uniform(0.80, 1.15) * quality_boost, 2),
        "actual_freq":  round(baseline_freq  * rng.uniform(0.88, 1.18) / quality_boost, 2),
        "actual_area":  round(baseline_area  * rng.uniform(0.82, 1.16) * quality_boost, 2),
    }
    flags = {
        "power_fail": actual["actual_power"] > targets["target_power"],
        "freq_fail":  actual["actual_freq"]  < targets["target_freq"],
        "area_fail":  actual["actual_area"]  > targets["target_area"],
    }
    return pred, actual, flags


def choose_action(flags, confidence, rng, is_last_suggestion=True):
    any_fail = flags["power_fail"] or flags["freq_fail"] or flags["area_fail"]
    if any_fail:
        if is_last_suggestion:
            action = rng.choices(["reject", "modify", "rollback"], weights=[0.50, 0.43, 0.07])[0]
        else:
            action = rng.choices(["reject", "modify"], weights=[0.55, 0.45])[0]
        reason = "ppa_violation"
    else:
        if confidence >= 0.80:
            action = rng.choices(["accept", "modify"], weights=[0.82, 0.18])[0]
        else:
            action = rng.choices(["accept", "modify"], weights=[0.60, 0.40])[0]
        reason = "meets_targets"
    return action, reason


def main(n_sessions: int = 500, out_dir: str = "data/telemetry/deep_sessions"):
    out_dir = Path(out_dir)
    artifacts_root = Path("artifacts/sessions")

    # Clear old sessions (safe per-file deletion)
    import shutil
    for p in Path(out_dir).glob("sess_*.jsonl"):
        try: p.unlink()
        except: pass
    mf = Path(out_dir) / "manifest.json"
    if mf.exists():
        try: mf.unlink()
        except: pass
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rtl_kinds = list(DESIGN_TARGETS.keys())
    seen_session_hashes = set()
    manifest = {"generated_at": now_iso(), "n_sessions": n_sessions, "sessions": []}

    generated = 0
    attempts = 0
    max_attempts = n_sessions * 3

    while generated < n_sessions and attempts < max_attempts:
        attempts += 1
        seed = (uuid.uuid4().int >> 96) ^ (generated * 2654435761)
        rng = random.Random(seed)

        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        kind = rng.choice(rtl_kinds)
        targets = DESIGN_TARGETS[kind]
        bp_lo, bp_hi, bf_lo, bf_hi, ba_lo, ba_hi = DESIGN_BASELINES[kind]

        baseline_power = rng.uniform(bp_lo, bp_hi)
        baseline_freq  = rng.uniform(bf_lo, bf_hi)
        baseline_area  = rng.uniform(ba_lo, ba_hi)
        baseline = {
            "baseline_power": round(baseline_power, 2),
            "baseline_freq":  round(baseline_freq,  2),
            "baseline_area":  round(baseline_area,  2),
        }

        # 1-3 suggestions per session
        n_suggestions = rng.choices([1, 2, 3], weights=[0.55, 0.30, 0.15])[0]

        events = [
            {"event_type": "session_start", "session_id": session_id, "timestamp": now_iso()},
            {
                "event_type": "design_context", "session_id": session_id, "timestamp": now_iso(),
                "design_id": f"design_{kind}_{generated}",
                "rtl_kind": kind,
                "top_module": f"design_{kind}_{generated}",
                "constraints_id": f"const_{kind}_{rng.randint(1,8)}",
                "eda_tool": {"name": "synthetic", "version": "0.3"},
            },
            {"event_type": "baseline_ppa", "session_id": session_id, "timestamp": now_iso(),
             **targets, **baseline},
        ]

        session_sugg_ids = []
        for rank in range(1, n_suggestions + 1):
            top_after = f"rewrite_{kind}_{generated}_v{rank}"
            rtl_before_text = rtl_template(kind, f"design_{kind}_{generated}")
            rtl_after_text  = rewrite_style(kind, top_after, variant=rank - 1)

            base_dir = artifacts_root / session_id
            rtl_before_ref = str(base_dir / "rtl_before.sv")
            rtl_after_ref  = str(base_dir / f"rtl_after_sugg_{rank}.sv")
            diff_ref       = str(base_dir / f"rtl_diff_sugg_{rank}.patch")

            write_text(Path(rtl_before_ref), rtl_before_text)
            write_text(Path(rtl_after_ref), rtl_after_text)
            # diff written on demand — skip file write to keep I/O fast

            suggestion_id = "sugg_" + uuid.uuid4().hex[:8]
            confidence    = round(rng.uniform(0.35, 0.95), 2)
            latency_ms    = rng.randint(400, 4500)

            pred, actual, flags = synth_ppa(
                baseline_power, baseline_freq, baseline_area, targets, rng, rank
            )
            is_last = (rank == n_suggestions)
            action, reason = choose_action(flags, confidence, rng, is_last)

            session_sugg_ids.append(suggestion_id)

            events += [
                {
                    "event_type": "suggestion_generated", "session_id": session_id,
                    "suggestion_id": suggestion_id, "timestamp": now_iso(),
                    "latency_ms": latency_ms, "confidence_score": confidence,
                    "goal": "optimize_ppa", "suggestion_rank": rank,
                    "rtl_before_ref": rtl_before_ref, "rtl_after_ref": rtl_after_ref,
                    "diff_ref": diff_ref, **pred,
                },
                {
                    "event_type": "evaluation_result", "session_id": session_id,
                    "suggestion_id": suggestion_id, "timestamp": now_iso(),
                    "tool_run": {"name": "synthetic_flow", "seed": seed},
                    **targets, **baseline, **actual, "ppa_flags": flags,
                },
                {
                    "event_type": "action_taken", "session_id": session_id,
                    "suggestion_id": suggestion_id, "timestamp": now_iso(),
                    "action": action, "action_reason": reason,
                },
            ]

        events.append({"event_type": "session_end", "session_id": session_id, "timestamp": now_iso()})

        sig = sha256_text(json.dumps({
            "kind": kind, "baseline": baseline, "n_sugg": n_suggestions,
            "sugg_ids": session_sugg_ids,
        }, sort_keys=True))
        if sig in seen_session_hashes:
            continue
        seen_session_hashes.add(sig)

        write_jsonl(out_dir / f"{session_id}.jsonl", events)
        manifest["sessions"].append({
            "session_id": session_id, "kind": kind,
            "n_suggestions": n_suggestions,
        })
        generated += 1

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated {generated} sessions ({sum(s.get('n_suggestions',1) for s in manifest['sessions'])} total suggestions) in: {out_dir}")


if __name__ == "__main__":
    main(n_sessions=150)
