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


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


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


# --- RTL templates (ensure sessions differ structurally, not just numbers) ---

def rtl_template(kind: str, top_name: str) -> str:
    """
    Returns a small SystemVerilog module string for a given kind.
    """
    if kind == "logic_combo_1":
        return f"""module {top_name}(input logic a,b,c, output logic y);
  assign y = (a & b) | c;
endmodule
"""
    if kind == "logic_combo_2":
        return f"""module {top_name}(input logic a,b,c, output logic y);
  assign y = (a | b) & (~c);
endmodule
"""
    if kind == "logic_combo_3":
        return f"""module {top_name}(input logic a,b,c, output logic y);
  assign y = (a ^ b) ^ c;
endmodule
"""
    if kind == "mux":
        return f"""module {top_name}(input logic sel, d0, d1, output logic y);
  assign y = sel ? d1 : d0;
endmodule
"""
    if kind == "adder4":
        return f"""module {top_name}(input logic [3:0] a,b, output logic [4:0] y);
  assign y = a + b;
endmodule
"""
    if kind == "small_fsm":
        return f"""module {top_name}(input logic clk, rst_n, in, output logic out);
  typedef enum logic [1:0] {{S0, S1, S2, S3}} state_t;
  state_t s, ns;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) s <= S0;
    else s <= ns;
  end

  always_comb begin
    ns = s;
    out = 1'b0;
    unique case (s)
      S0: ns = in ? S1 : S0;
      S1: ns = in ? S2 : S0;
      S2: begin ns = in ? S3 : S0; out = 1'b1; end
      S3: ns = in ? S3 : S0;
    endcase
  end
endmodule
"""
    raise ValueError(f"Unknown rtl kind: {kind}")


def rewrite_style(kind: str, top_name: str) -> str:
    """
    Creates a "copilot rewrite" that is functionally equivalent but structurally different.
    (Still synthetic, but meaningfully different.)
    """
    if kind == "logic_combo_1":
        return f"""module {top_name}(input logic a,b,c, output logic y);
  logic t;
  assign t = a & b;
  assign y = t | c;
endmodule
"""
    if kind == "logic_combo_2":
        return f"""module {top_name}(input logic a,b,c, output logic y);
  logic t;
  assign t = a | b;
  assign y = t & ~c;
endmodule
"""
    if kind == "logic_combo_3":
        return f"""module {top_name}(input logic a,b,c, output logic y);
  logic t;
  assign t = a ^ b;
  assign y = t ^ c;
endmodule
"""
    if kind == "mux":
        # same mux, but rewritten as boolean equations
        return f"""module {top_name}(input logic sel, d0, d1, output logic y);
  assign y = (~sel & d0) | (sel & d1);
endmodule
"""
    if kind == "adder4":
        # Introduce an intermediate wire; still equivalent
        return f"""module {top_name}(input logic [3:0] a,b, output logic [4:0] y);
  logic [4:0] aa, bb;
  assign aa = {{1'b0,a}};
  assign bb = {{1'b0,b}};
  assign y = aa + bb;
endmodule
"""
    if kind == "small_fsm":
        # Same FSM, but with slightly different formatting / explicit defaults
        return f"""module {top_name}(input logic clk, rst_n, in, output logic out);
  typedef enum logic [1:0] {{S0, S1, S2, S3}} state_t;
  state_t s, ns;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) s <= S0;
    else s <= ns;
  end

  always_comb begin
    ns = s;
    out = 1'b0;
    unique case (s)
      S0: begin
        if (in) ns = S1;
        else ns = S0;
      end
      S1: begin
        if (in) ns = S2;
        else ns = S0;
      end
      S2: begin
        out = 1'b1;
        if (in) ns = S3;
        else ns = S0;
      end
      default: begin
        if (in) ns = S3;
        else ns = S0;
      end
    endcase
  end
endmodule
"""
    raise ValueError(f"Unknown rtl kind: {kind}")


def synth_ppa(baseline_power, baseline_freq, baseline_area, targets, rng: random.Random):
    """
    Generate predicted + actual PPA. Keeps relationships realistic-ish and noisy.
    """
    # predicted (model estimate)
    pred = {
        "pred_power": round(baseline_power * rng.uniform(0.85, 1.03), 2),
        "pred_freq": round(baseline_freq * rng.uniform(0.95, 1.12), 2),
        "pred_area": round(baseline_area * rng.uniform(0.88, 1.06), 2),
    }
    # actual (tool-measured)
    actual = {
        "actual_power": round(baseline_power * rng.uniform(0.82, 1.12), 2),
        "actual_freq": round(baseline_freq * rng.uniform(0.90, 1.15), 2),
        "actual_area": round(baseline_area * rng.uniform(0.84, 1.14), 2),
    }

    power_fail = actual["actual_power"] > targets["target_power"]
    freq_fail = actual["actual_freq"] < targets["target_freq"]
    area_fail = actual["actual_area"] > targets["target_area"]

    return pred, actual, {"power_fail": power_fail, "freq_fail": freq_fail, "area_fail": area_fail}


def choose_action(flags, confidence, rng: random.Random):
    # If PPA violates targets, more likely reject/modify
    if flags["power_fail"] or flags["freq_fail"] or flags["area_fail"]:
        action = rng.choices(["reject", "modify"], weights=[0.55, 0.45])[0]
        reason = "ppa_violation"
    else:
        # If meets, more likely accept (esp. if confidence high)
        if confidence >= 0.8:
            action = rng.choices(["accept", "modify"], weights=[0.8, 0.2])[0]
        else:
            action = rng.choices(["accept", "modify"], weights=[0.55, 0.45])[0]
        reason = "meets_targets"
    return action, reason


def main(n_sessions: int = 50, out_dir: str = "data/telemetry/deep_sessions"):
    out_dir = Path(out_dir)
    artifacts_root = Path("artifacts/sessions")

    rtl_kinds = ["logic_combo_1", "logic_combo_2", "logic_combo_3", "mux", "adder4", "small_fsm"]

    # Uniqueness guards
    seen_session_hashes = set()
    seen_rtl_pair_hashes = set()

    manifest = {
        "generated_at": now_iso(),
        "n_sessions": n_sessions,
        "sessions": []
    }

    for i in range(n_sessions):
        # unique RNG per session
        seed = (uuid.uuid4().int >> 96) ^ (i * 2654435761)
        rng = random.Random(seed)

        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        base_dir = artifacts_root / session_id
        jsonl_path = out_dir / f"{session_id}.jsonl"

        kind = rng.choice(rtl_kinds)

        # vary top names too
        top_before = f"design_{kind}_{i}"
        top_after = f"rewrite_{kind}_{i}"

        rtl_before = rtl_template(kind, top_before)
        rtl_after = rewrite_style(kind, top_after)

        rtl_pair_sig = sha256_text(rtl_before + "\n---\n" + rtl_after)
        if rtl_pair_sig in seen_rtl_pair_hashes:
            # extremely unlikely, but keep it strict
            continue
        seen_rtl_pair_hashes.add(rtl_pair_sig)

        rtl_before_ref = str(base_dir / "rtl_before.sv")
        rtl_after_ref = str(base_dir / "rtl_after_sugg_1.sv")
        diff_ref = str(base_dir / "rtl_diff_sugg_1.patch")

        write_text(Path(rtl_before_ref), rtl_before)
        write_text(Path(rtl_after_ref), rtl_after)
        write_text(Path(diff_ref), make_diff(rtl_before, rtl_after))

        targets = {"target_power": 750, "target_freq": 2400, "target_area": 11}

        # baseline varies by design kind so sessions feel different
        if kind == "adder4":
            baseline_power = rng.uniform(700, 980)
            baseline_freq = rng.uniform(1800, 2500)
            baseline_area = rng.uniform(10.5, 14.0)
        elif kind == "small_fsm":
            baseline_power = rng.uniform(600, 900)
            baseline_freq = rng.uniform(1500, 2400)
            baseline_area = rng.uniform(8.5, 12.5)
        else:
            baseline_power = rng.uniform(550, 950)
            baseline_freq = rng.uniform(1700, 2600)
            baseline_area = rng.uniform(8.0, 13.5)

        baseline = {
            "baseline_power": round(baseline_power, 2),
            "baseline_freq": round(baseline_freq, 2),
            "baseline_area": round(baseline_area, 2),
        }

        suggestion_id = "sugg_" + uuid.uuid4().hex[:8]
        confidence = round(rng.uniform(0.45, 0.95), 2)
        latency_ms = rng.randint(500, 3500)

        pred, actual, flags = synth_ppa(baseline["baseline_power"], baseline["baseline_freq"], baseline["baseline_area"], targets, rng)
        action, reason = choose_action(flags, confidence, rng)

        # strong session signature for dedupe
        session_sig = sha256_text(json.dumps({
            "kind": kind,
            "baseline": baseline,
            "pred": pred,
            "actual": actual,
            "confidence": confidence,
            "latency": latency_ms,
            "action": action,
            "reason": reason,
            "rtl_pair_sig": rtl_pair_sig
        }, sort_keys=True))

        if session_sig in seen_session_hashes:
            continue
        seen_session_hashes.add(session_sig)

        events = [
            {"event_type": "session_start", "session_id": session_id, "timestamp": now_iso()},
            {
                "event_type": "design_context",
                "session_id": session_id,
                "timestamp": now_iso(),
                "design_id": f"design_{kind}_{i}",
                "rtl_kind": kind,
                "top_module": top_before,
                "constraints_id": f"const_demo_{rng.randint(1, 5)}",
                "eda_tool": {"name": "synthetic", "version": "0.2"},
            },
            {
                "event_type": "baseline_ppa",
                "session_id": session_id,
                "timestamp": now_iso(),
                **targets,
                **baseline,
            },
            {
                "event_type": "suggestion_generated",
                "session_id": session_id,
                "suggestion_id": suggestion_id,
                "timestamp": now_iso(),
                "latency_ms": latency_ms,
                "confidence_score": confidence,
                "goal": "optimize_ppa",
                "rtl_before_ref": rtl_before_ref,
                "rtl_after_ref": rtl_after_ref,
                "diff_ref": diff_ref,
                **pred,
            },
            {
                "event_type": "evaluation_result",
                "session_id": session_id,
                "suggestion_id": suggestion_id,
                "timestamp": now_iso(),
                "tool_run": {"name": "synthetic_flow", "seed": seed},
                **targets,
                **baseline,
                **actual,
                "ppa_flags": flags,
            },
            {
                "event_type": "action_taken",
                "session_id": session_id,
                "suggestion_id": suggestion_id,
                "timestamp": now_iso(),
                "action": action,
                "action_reason": reason,
            },
            {"event_type": "session_end", "session_id": session_id, "timestamp": now_iso()},
        ]

        write_jsonl(jsonl_path, events)

        manifest["sessions"].append({
            "session_id": session_id,
            "jsonl": str(jsonl_path),
            "artifacts_dir": str(base_dir),
            "rtl_pair_sig": rtl_pair_sig,
            "session_sig": session_sig,
            "kind": kind,
            "action": action,
            "confidence": confidence,
            "ppa_flags": flags,
        })

    # write manifest
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Generated {len(manifest['sessions'])} deep sessions in: {out_dir}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main(n_sessions=50)
