# Silimate Copilot — QA Intelligence Framework

> An independent, speculative QA framework inspired by Silimate's mission to compress chip design
> cycles from 12–18 months to under 6 months. All data is synthetic. No proprietary information used.

---

## What This Is

Most AI engineering portfolios show a chatbot or a fine-tuned model. This project does something different: it treats Silimate's RTL copilot as a **production AI system that needs observability, calibration, and a feedback loop** — and builds the infrastructure to deliver all three.

The core question: *how do you know if an AI that generates SystemVerilog is actually getting better?*

This framework answers that with an 8-stage QA pipeline across 1,698 suggestions, 8 RTL design types, and a live Flask dashboard — combined into a single trackable **Copilot Quality Index (CQI)**.

---

## Live Dashboard

![Dashboard screenshot showing CQI 0.2535/F, 1698 sessions, PPA pass 9.8%, Brier 0.44](docs/dashboard.png)

**What you see:** CQI 0.2535 / Grade F. Sessions: 1,698. PPA pass rate: 9.8%. Brier: 0.44. Mean latency: 2,461ms. P95: 4,290ms.

This is the correct output — the copilot is confidently wrong 90% of the time. The framework's job is to **surface that fact, quantify it, and point to the fix**.

---

## Architecture

```
Telemetry JSONL
  (1,067 sessions — 8 RTL design types, 1–3 suggestions each)
        │
        ▼
┌─────────────────────────────┐
│  session_qa_analyzer.py     │  ← Stage 1 (cached — skips re-parse if CSV fresh)
│  • PPA fail mode detection  │
│  • Action alignment check   │
│  • RTL feature extraction   │
│  • Pred error extraction    │
└────────────┬────────────────┘
             │
    ┌────────┴──────────────────────────────────────────┐
    ▼                ▼              ▼                    ▼
calibration.py  prediction_   feedback_loop.py   session_clustering.py
• Brier 0.44    error_        • Logistic regr.   • k-means failure
• ECE 0.59      analyzer.py     on 1,698 real      pattern detection
• OVERCONF      • MAPE 9.83%    suggestions      • 4 clusters
                • power bias  • ppa_pass=0.797   • auto-labeling
    │                │              │                    │
    └────────────────┴──────────────┴────────────────────┘
                          │
          ┌───────────────┴─────────────────┐
          ▼                                 ▼
  copilot_quality_index.py          recalibrator.py
  • CQI 0.2535 / Grade F           • Isotonic regression
  • Per-design-type CQI            • Brier 0.44 → 0.06
  • small_fsm gets F                 (85.9% improvement)
          │
          ▼
  make_rankings.py           Flask Dashboard
  • Pre-EDA scoring          /api/metrics  /api/sessions
  • 57.9% WARN flagged       Chart.js — dark theme
  • Ranks before EDA runs    Live at localhost:5000
```

---

## Key Numbers (from real pipeline run)

| Metric | Value | What it means |
|---|---|---|
| Sessions analyzed | 1,698 suggestions | Enough for credible ML |
| PPA pass rate | **9.8%** | Copilot fails targets 90% of the time |
| Acceptance rate | 6.4% | Users accept very few suggestions as-is |
| Brier score | **0.44** | Worse than random (0.25) — severely overconfident |
| After recalibration | **0.06** | 85.9% improvement with isotonic regression |
| Avg confidence | 0.66 | Copilot thinks it's right 66% — actually right 6% |
| Mean latency | 2,461ms | Under SLA; P95 = 4,290ms spikes above |
| ppa_pass feature weight | **0.797** | PPA compliance drives 80% of acceptance decisions |
| Weakest design type | small_fsm / F | FAIL_POWER_AREA dominant |
| Pre-EDA WARN flags | **57.9%** | Caught before wasting EDA compute |

---

## Eight Quality Signals

### 1. Confidence Calibration — Brier Score + ECE
Measures whether `confidence=0.80` actually means "accepted 80% of the time." Brier = 0.44 means the copilot is systematically overconfident across all four confidence buckets.

### 2. Isotonic Recalibration
Fits `IsotonicRegression` on (raw_confidence, accept_outcome) pairs. Reduces Brier from **0.44 → 0.06** — production-ready confidence remapping. Re-fit on every new batch.

### 3. LLM PPA Prediction Error Analysis
The copilot emits `pred_power/freq/area` before EDA runs. This module measures how wrong those predictions are:
- Power dimension: MAPE 10.8%, bias -24.7µW (underestimates power → over-approves failing suggestions)
- All 8 design types analyzed separately

### 4. Feedback Loop — Acceptance Predictor
Logistic regression trained on 1,698 real suggestions. Feature importances:
```
ppa_pass              0.797  ← PPA compliance is almost everything
pred_error_area_norm  0.095
confidence            0.064  ← raw confidence barely matters
```

### 5. Copilot Quality Index (CQI)
```
CQI = 0.30 × ppa_pass_rate       (9.8%)
    + 0.20 × calibration_quality  (0.0% — Brier worse than random)
    + 0.15 × latency_sla_rate     (61.9%)
    + 0.20 × adjusted_acceptance  (65.7%)
    + 0.15 × pred_accuracy        (0.0% — dashboard inline calc)
= 0.2535 / Grade F
```

### 6. Per-Design-Type CQI
| Design | CQI | Grade | Dominant Fail |
|---|---|---|---|
| small_fsm | 0.3313 | **F** | FAIL_POWER_AREA |
| adder4 | 0.3782 | D | FAIL_POWER_FREQ_AREA |
| shifter | 0.4157 | D | FAIL_POWER_AREA |
| mux | 0.4483 | D | FAIL_POWER_AREA |

**Fix FSM rewrites first** — highest leverage, currently the worst type.

### 7. Session Clustering
k-means on `[confidence, latency, ppa_pass, ppa_deltas, pred_errors]` reveals that **90.2% of failures are power-related** — one targeted fix (power model improvement) has 9× leverage on overall CQI.

### 8. Pre-EDA Suggestion Ranking
Scores suggestions using the fitted logistic model *before* EDA runs. 57.9% of suggestions are flagged WARN (`accept_prob < 0.30`) — those can be re-prompted or shown with a warning, saving expensive EDA compute cycles.

---

## Quick Start

```bash
# 1. Install dependencies (minimal)
pip install -r requirements.txt

# 2. Generate synthetic telemetry
cd scripts/
python generate_deep_session.py    # ~150 sessions, 8 design types

# 3. Run full 8-stage pipeline
python run_session_qa.py           # stage 1 cached after first run

# 4. Launch dashboard
set PYTHONPATH=..\silimatespecvalidator   # Windows CMD
python -c "from specvalidator.dashboard.app import app; app.run(port=5000)"
# → http://localhost:5000

# 5. Score new suggestions before EDA (pre-EDA ranker)
python make_rankings.py
```

---

## Project Structure

```
Silimate Insights/
├── requirements.txt
├── README.md
│
├── scripts/
│   ├── run_session_qa.py              ← 8-stage pipeline entry point
│   ├── generate_deep_session.py       ← synthetic telemetry generator
│   ├── make_rankings.py               ← pre-EDA suggestion scorer
│   ├── data/telemetry/deep_sessions/  ← JSONL session files (sample in repo)
│   └── reports/
│       ├── session_qa_results.csv     ← per-suggestion detail
│       └── session_qa_summary.txt     ← action / fail-mode distributions
│
└── silimatespecvalidator/
    └── specvalidator/
        ├── core/
        │   ├── session_qa_analyzer.py       ← Stage 1: telemetry → records
        │   ├── session_clustering.py        ← Stage 6: k-means patterns
        │   └── rtl_features.py              ← SystemVerilog feature extraction
        │
        ├── quality_metrics/
        │   ├── calibration.py               ← Stage 2: Brier + ECE
        │   ├── prediction_error_analyzer.py ← Stage 3: LLM PPA accuracy
        │   ├── feedback_loop.py             ← Stage 4: logistic regression
        │   ├── copilot_quality_index.py     ← Stage 5: CQI + per-type
        │   └── recalibrator.py              ← Stage 7: isotonic remapping
        │
        ├── dashboard/
        │   ├── app.py                       ← Flask REST API
        │   └── templates/index.html         ← Chart.js dark dashboard
        │
        └── eda_integration/                 ← EDA tool abstraction layer
```

---

## Telemetry Schema

```jsonl
{"event_type": "session_start",        "session_id": "sess_037a61e4"}
{"event_type": "design_context",       "rtl_kind": "small_fsm", "eda_tool": {...}}
{"event_type": "baseline_ppa",         "target_power": 650, "baseline_power": 720.1}
{"event_type": "suggestion_generated", "confidence_score": 0.83, "latency_ms": 2847,
                                        "pred_power": 598.1, "suggestion_rank": 2}
{"event_type": "evaluation_result",    "actual_power": 721.4, "ppa_flags": {...}}
{"event_type": "action_taken",         "action": "reject", "action_reason": "ppa_violation"}
{"event_type": "session_end"}
```

`suggestion_rank` enables multi-suggestion-per-session analysis.

---

## Concepts Demonstrated

| Concept | File |
|---|---|
| Probabilistic calibration (Brier score + ECE) | `calibration.py` |
| Isotonic regression confidence remapping | `recalibrator.py` |
| LLM output accuracy by design type | `prediction_error_analyzer.py` |
| Feedback loop: telemetry → model refit | `feedback_loop.py` |
| Composite AI health metric + per-type breakdown | `copilot_quality_index.py` |
| k-means failure taxonomy + auto-labeling | `session_clustering.py` |
| Pre-EDA inference pipeline | `make_rankings.py` |
| Incremental pipeline caching | `run_session_qa.py` |
| Event-driven telemetry schema | `data/telemetry/` |
| Flask REST API + Chart.js dashboard | `dashboard/` |

---

## Stack

Python 3.12 · scikit-learn · Flask · Chart.js · SystemVerilog

---

Contact: Prathyusha · prathyushamardhi3@gmail.com · Open to AI Engineer roles
