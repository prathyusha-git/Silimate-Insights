# silimatespecvalidator/specvalidator/dashboard/app.py
"""
Silimate Copilot QA Dashboard
Serves all quality metrics via JSON API, rendered by a self-contained HTML frontend.
"""

from flask import Flask, jsonify, send_from_directory
from pathlib import Path
import json
import sys

app = Flask(__name__, static_folder=None)

# ── Resolve project paths ────────────────────────────────────────────────────
# This file: silimatespecvalidator/specvalidator/dashboard/app.py
# parents[3] = Silimate Insights root
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parents[3]
_SCRIPTS = _PROJECT_ROOT / "scripts"
_REPORTS = _SCRIPTS / "reports"
_TEMPLATE = _HERE.parent / "templates" / "index.html"


def _load_json(path: Path):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _run_analysis_if_needed():
    """Run the full pipeline if reports don't exist yet."""
    if not (_REPORTS / "session_qa_results.json").exists():
        sys.path.insert(0, str(_PROJECT_ROOT / "silimatespecvalidator"))
        sys.path.insert(0, str(_SCRIPTS))
        from specvalidator.core.session_qa_analyzer import analyze_all_sessions
        import os
        orig = os.getcwd()
        os.chdir(_SCRIPTS)
        analyze_all_sessions(
            sessions_folder="data/telemetry/deep_sessions",
            artifacts_folder="artifacts/sessions",
            out_folder="reports",
        )
        os.chdir(orig)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    _run_analysis_if_needed()
    if _TEMPLATE.exists():
        return _TEMPLATE.read_text(encoding="utf-8")
    return "<h1>Dashboard template missing — run from specvalidator.dashboard</h1>", 500


@app.route("/api/sessions")
def get_sessions():
    data = _load_json(_REPORTS / "session_qa_results.json")
    if data is None:
        return jsonify({"status": "error", "message": "No data — run analysis first"}), 404
    return jsonify({"status": "ok", "sessions": data})


@app.route("/api/summary")
def get_summary():
    """Parse the text summary into structured JSON for the dashboard."""
    path = _REPORTS / "session_qa_summary.txt"
    if not path.exists():
        return jsonify({"status": "error"}), 404
    return jsonify({"status": "ok", "content": path.read_text(encoding="utf-8")})


@app.route("/api/metrics")
def get_metrics():
    """Compute and return all quality metrics as JSON."""
    data = _load_json(_REPORTS / "session_qa_results.json")
    if data is None:
        return jsonify({"status": "error", "message": "No data"}), 404

    # Reconstruct lightweight record-like dicts — avoids re-importing heavy modules
    records = data

    # ── Action distribution ───────────────────────────────────────────────────
    actions: dict = {}
    fail_modes: dict = {}
    latencies = []
    confidences = []
    accepted, total = 0, 0
    ppa_pass = 0
    pred_errors_power, pred_errors_freq, pred_errors_area = [], [], []
    rtl_kinds: dict = {}

    for r in records:
        a = r.get("action", "unknown")
        actions[a] = actions.get(a, 0) + 1
        fm = r.get("fail_mode", "UNKNOWN")
        fail_modes[fm] = fail_modes.get(fm, 0) + 1

        lat = r.get("latency_ms")
        if lat is not None:
            latencies.append(lat)

        conf = r.get("confidence")
        if conf is not None:
            confidences.append(conf)

        if a == "accept":
            accepted += 1
        total += 1

        if fm == "PASS":
            ppa_pass += 1

        for dim, key in [("power", "pred_error_power"), ("freq", "pred_error_freq"), ("area", "pred_error_area")]:
            v = r.get(key)
            if v is not None:
                if dim == "power":
                    pred_errors_power.append(v)
                elif dim == "freq":
                    pred_errors_freq.append(v)
                else:
                    pred_errors_area.append(v)

        kind = r.get("rtl_kind") or "unknown"
        rtl_kinds[kind] = rtl_kinds.get(kind, 0) + 1

    def mean(lst):
        return sum(lst) / len(lst) if lst else None

    def mae(lst):
        return sum(abs(x) for x in lst) / len(lst) if lst else None

    # Calibration buckets for chart
    cal_buckets = []
    bucket_edges = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.65), (0.65, 0.8), (0.8, 1.01)]
    for lo, hi in bucket_edges:
        members = [
            r for r in records
            if r.get("confidence") is not None and lo <= r["confidence"] < hi
        ]
        if members:
            acc_rate = sum(1 for r in members if r.get("action") == "accept") / len(members)
            avg_conf = mean([r["confidence"] for r in members])
            cal_buckets.append({
                "label": f"{lo:.2f}-{hi:.2f}",
                "avg_confidence": round(avg_conf, 3),
                "actual_acceptance": round(acc_rate, 3),
                "n": len(members),
            })

    # Simple Brier score
    valid_cal = [(r["confidence"], 1 if r.get("action") == "accept" else 0)
                 for r in records if r.get("confidence") is not None]
    brier = round(sum((c - o) ** 2 for c, o in valid_cal) / len(valid_cal), 4) if valid_cal else None

    # CQI components (simplified inline)
    ppa_pass_rate = ppa_pass / total if total else 0
    cal_score = max(0, 1 - (brier or 0.25) / 0.25) if brier else 0.5
    lat_sla_rate = sum(1 for l in latencies if l <= 3000) / len(latencies) if latencies else 0.5
    ppa_pass_recs = [r for r in records if r.get("fail_mode") == "PASS"]
    adj_accept = (sum(1 for r in ppa_pass_recs if r.get("action") == "accept") / len(ppa_pass_recs)
                  if ppa_pass_recs else 0)
    pred_mape_power = mae(pred_errors_power) / 100 if pred_errors_power else 0.5
    pred_acc = max(0, 1 - min(pred_mape_power, 0.5) / 0.5)

    cqi = round(
        0.30 * ppa_pass_rate
        + 0.20 * cal_score
        + 0.15 * lat_sla_rate
        + 0.20 * adj_accept
        + 0.15 * pred_acc,
        4,
    )
    grade = "A" if cqi >= 0.80 else "B" if cqi >= 0.65 else "C" if cqi >= 0.50 else "D" if cqi >= 0.35 else "F"

    return jsonify({
        "status": "ok",
        "n_sessions": total,
        "actions": actions,
        "fail_modes": fail_modes,
        "rtl_kinds": rtl_kinds,
        "acceptance_rate": round(accepted / total, 4) if total else 0,
        "ppa_pass_rate": round(ppa_pass_rate, 4),
        "mean_latency_ms": round(mean(latencies), 1) if latencies else None,
        "p95_latency_ms": sorted(latencies)[int(0.95 * len(latencies))] if len(latencies) > 10 else None,
        "mean_confidence": round(mean(confidences), 4) if confidences else None,
        "brier_score": brier,
        "calibration_buckets": cal_buckets,
        "pred_error_mae": {
            "power": round(mae(pred_errors_power), 3) if pred_errors_power else None,
            "freq": round(mae(pred_errors_freq), 3) if pred_errors_freq else None,
            "area": round(mae(pred_errors_area), 3) if pred_errors_area else None,
        },
        "cqi": cqi,
        "cqi_grade": grade,
        "cqi_components": {
            "ppa_pass_rate": round(ppa_pass_rate, 4),
            "calibration_score": round(cal_score, 4),
            "latency_sla_rate": round(lat_sla_rate, 4),
            "adjusted_acceptance": round(adj_accept, 4),
            "pred_accuracy": round(pred_acc, 4),
        },
    })


class DashboardApp:
    def __init__(self, data_path: Path = _REPORTS):
        self.data_path = data_path

    def run(self, host="0.0.0.0", port=5000, debug=False):
        print(f"  Dashboard: http://localhost:{port}")
        app.run(host=host, port=port, debug=debug)
