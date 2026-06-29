"""
Feedback Loop: Fit AcceptancePredictor on real telemetry data.

Replaces the hardcoded weights in AcceptancePredictor with a logistic
regression trained on observed outcomes. This closes the AI engineering
feedback loop:

  telemetry → analyze → calibrate → fit model → updated predictor → better suggestions

Feature vector per suggestion:
  [confidence, ppa_pass, latency_norm, pred_error_power_norm,
   pred_error_freq_norm, pred_error_area_norm]

Label: 1 = accepted, 0 = rejected or modified
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import json
from pathlib import Path


@dataclass
class FitResult:
    n_train: int
    n_pos: int                      # accepted
    n_neg: int                      # rejected/modified
    feature_names: List[str]
    feature_importances: Dict[str, float]  # coefficient magnitudes (normalised)
    train_accuracy: float
    intercept: float
    verdict: str                    # FITTED / INSUFFICIENT_DATA / SKEWED_LABELS


FEATURE_NAMES = [
    "confidence",
    "ppa_pass",
    "latency_norm",           # latency_ms / 5000 (clamped)
    "pred_error_power_norm",  # |pred_error_power| / 100
    "pred_error_freq_norm",   # |pred_error_freq| / 500
    "pred_error_area_norm",   # |pred_error_area| / 5
]


def _extract_features(record: Any) -> Optional[List[float]]:
    """Extract normalised feature vector from a SuggestionRecord."""
    if record.confidence is None:
        return None
    lat = record.latency_ms or 1000
    return [
        float(record.confidence),
        1.0 if record.fail_mode == "PASS" else 0.0,
        min(1.0, lat / 5000.0),
        abs(record.pred_error_power or 0.0) / 100.0,
        abs(record.pred_error_freq or 0.0) / 500.0,
        abs(record.pred_error_area or 0.0) / 5.0,
    ]


def fit_acceptance_model(records: List[Any]) -> Tuple[Any, FitResult]:
    """
    Fit a logistic regression on SuggestionRecord list.
    Returns (fitted_sklearn_model, FitResult).

    Usage:
        model, result = fit_acceptance_model(records)
        prob = model.predict_proba([[conf, ppa_pass, lat_norm, ...]])[0][1]
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        import numpy as np
    except ImportError:
        raise ImportError("scikit-learn required: pip install scikit-learn")

    X_raw, y = [], []
    for r in records:
        feats = _extract_features(r)
        if feats is None:
            continue
        label = 1 if r.action == "accept" else 0
        X_raw.append(feats)
        y.append(label)

    n_pos = sum(y)
    n_neg = len(y) - n_pos

    if len(y) < 10:
        return None, FitResult(
            n_train=len(y), n_pos=n_pos, n_neg=n_neg,
            feature_names=FEATURE_NAMES,
            feature_importances={f: 0.0 for f in FEATURE_NAMES},
            train_accuracy=float("nan"),
            intercept=0.0,
            verdict="INSUFFICIENT_DATA",
        )

    if n_pos == 0 or n_neg == 0:
        return None, FitResult(
            n_train=len(y), n_pos=n_pos, n_neg=n_neg,
            feature_names=FEATURE_NAMES,
            feature_importances={f: 0.0 for f in FEATURE_NAMES},
            train_accuracy=float("nan"),
            intercept=0.0,
            verdict="SKEWED_LABELS",
        )

    X = np.array(X_raw)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(max_iter=500, class_weight="balanced", random_state=42)),
    ])
    model.fit(X, y)

    train_acc = float(np.mean(model.predict(X) == np.array(y)))

    # Feature importances: abs(coef) normalised to sum=1
    coefs = model.named_steps["lr"].coef_[0]
    abs_coefs = [abs(c) for c in coefs]
    total = sum(abs_coefs) or 1.0
    importances = {name: round(abs_c / total, 4) for name, abs_c in zip(FEATURE_NAMES, abs_coefs)}

    return model, FitResult(
        n_train=len(y),
        n_pos=n_pos,
        n_neg=n_neg,
        feature_names=FEATURE_NAMES,
        feature_importances=importances,
        train_accuracy=round(train_acc, 4),
        intercept=round(float(model.named_steps["lr"].intercept_[0]), 4),
        verdict="FITTED",
    )


def format_fit_report(result: FitResult) -> str:
    lines = [
        "Acceptance Predictor — Fit Results (trained on real telemetry)",
        "=" * 60,
        f"  Status:         {result.verdict}",
        f"  Training N:     {result.n_train}  (accepted={result.n_pos}, rejected/modified={result.n_neg})",
        f"  Train accuracy: {result.train_accuracy:.2%}" if result.verdict == "FITTED" else "",
        f"  Intercept:      {result.intercept}",
        "",
        "  Feature Importances (relative, sums to 1.0):",
        f"  {'Feature':<30} {'Importance':>12}",
        "  " + "-" * 45,
    ]
    if result.verdict == "FITTED":
        for feat, imp in sorted(result.feature_importances.items(), key=lambda x: -x[1]):
            bar = "█" * int(imp * 30)
            lines.append(f"  {feat:<30} {imp:>12.4f}  {bar}")
    else:
        lines.append(f"  Cannot compute importances: {result.verdict}")

    lines += [
        "",
        "  Interpretation: features with high importance drive acceptance/rejection.",
        "  'ppa_pass' dominating → users primarily care about PPA compliance.",
        "  'confidence' dominating → users trust the copilot's own assessment.",
        "  'pred_error_*' dominating → users are sensitive to LLM prediction accuracy.",
    ]
    return "\n".join(lines)


def save_model(model: Any, path: Path) -> None:
    """Persist the fitted model using joblib."""
    try:
        import joblib
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, path)
    except ImportError:
        pass  # joblib optional


def load_model(path: Path) -> Optional[Any]:
    """Load a persisted model."""
    try:
        import joblib
        if path.exists():
            return joblib.load(path)
    except Exception:
        pass
    return None
