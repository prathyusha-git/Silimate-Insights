"""
Session Clustering: find systematic failure patterns in copilot suggestions.

Uses k-means on a feature vector of [RTL deltas + PPA deltas + latency + confidence]
to group sessions into behavioural clusters. Each cluster is auto-labelled based on
which features dominate.

This answers: "Are there recurring patterns in how the copilot fails, or is each
failure idiosyncratic?" If we find a cluster like "10 sessions all failed FREQ due to
added pipeline stages", that's an actionable signal to improve the copilot's timing model.

Feature vector per session:
  [confidence, latency_norm, ppa_pass, delta_power_norm, delta_freq_norm,
   delta_area_norm, pred_error_power_norm, pred_error_freq_norm, pred_error_area_norm]
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import math


@dataclass
class SessionCluster:
    cluster_id: int
    label: str                          # human-readable cluster name
    n: int
    member_session_ids: List[str]
    centroid: Dict[str, float]          # mean feature values
    dominant_fail_mode: str             # most common fail_mode in cluster
    dominant_action: str                # most common action in cluster
    rtl_kinds: Dict[str, int]           # distribution of rtl_kind in cluster
    mean_confidence: float
    mean_latency_ms: Optional[float]
    ppa_pass_rate: float


@dataclass
class ClusteringResult:
    n_clusters: int
    clusters: List[SessionCluster]
    inertia: float
    silhouette_score: Optional[float]
    feature_names: List[str]
    verdict: str


FEATURE_NAMES = [
    "confidence",
    "latency_norm",
    "ppa_pass",
    "delta_power_norm",
    "delta_freq_norm",
    "delta_area_norm",
    "pred_error_power_norm",
    "pred_error_freq_norm",
    "pred_error_area_norm",
]


def _extract_vector(record: Any) -> Optional[List[float]]:
    """Build feature vector for clustering. Returns None if critical fields missing."""
    if record.confidence is None:
        return None
    lat = (record.latency_ms or 1000) / 5000.0

    def norm(v, scale):
        return (v or 0.0) / scale

    return [
        float(record.confidence),
        min(1.0, lat),
        1.0 if record.fail_mode == "PASS" else 0.0,
        norm(record.delta_power, 200.0),
        norm(record.delta_freq, 500.0),
        norm(record.delta_area, 5.0),
        norm(abs(record.pred_error_power or 0.0), 100.0),
        norm(abs(record.pred_error_freq or 0.0), 500.0),
        norm(abs(record.pred_error_area or 0.0), 5.0),
    ]


def _auto_label(centroid: Dict[str, float], dominant_fail: str, dominant_action: str) -> str:
    """
    Generate a human-readable label for a cluster.

    Priority order:
      1. Healthy cluster (PPA passes, accepted)
      2. PPA failure type (what dimension failed — most specific signal)
      3. Prediction error dimension (which PPA dim the LLM misjudges most)
      4. Behavioral pattern (latency, confidence, action)
    """
    ppa_pass = centroid.get("ppa_pass", 0)
    conf     = centroid.get("confidence", 0.5)
    lat      = centroid.get("latency_norm", 0)
    dp       = centroid.get("delta_power_norm", 0)   # pos = power went up
    df       = centroid.get("delta_freq_norm", 0)    # neg = freq went down
    da       = centroid.get("delta_area_norm", 0)    # pos = area went up

    pe_power = centroid.get("pred_error_power_norm", 0)
    pe_freq  = centroid.get("pred_error_freq_norm", 0)
    pe_area  = centroid.get("pred_error_area_norm", 0)
    max_pe   = max(pe_power, pe_freq, pe_area)

    # 1. Healthy cluster
    if ppa_pass > 0.6 and dominant_action in ("accept", "modify"):
        return "HEALTHY_ACCEPT"

    # 2. PPA failure — use the dominant_fail field directly (most reliable signal)
    #    rather than centroid deltas which can be noisy.
    if dominant_fail == "FAIL_POWER_FREQ_AREA":
        return "FULL_PPA_FAIL"
    if dominant_fail == "FAIL_POWER_FREQ":
        # Check what the LLM misjudges more: power or timing
        if pe_freq > pe_power * 1.3:
            return "POWER_FREQ_FAIL__TIMING_MODEL_WEAK"
        return "POWER_FREQ_FAIL__TRADEOFF_BLIND"
    if dominant_fail == "FAIL_FREQ" or dominant_fail == "FAIL_FREQ_AREA":
        if pe_freq > 0.15 and pe_freq >= max_pe * 0.7:
            return "TIMING_FAIL__FREQ_MODEL_UNRELIABLE"
        return "TIMING_REGRESSION"
    if dominant_fail == "FAIL_POWER" or dominant_fail == "FAIL_POWER_AREA":
        if pe_power > 0.15 and pe_power >= max_pe * 0.7:
            return "POWER_FAIL__POWER_MODEL_UNRELIABLE"
        return "POWER_HUNGRY"
    if dominant_fail == "FAIL_AREA":
        return "AREA_BLOAT"

    # 3. Prediction error dominates even if PPA passes (model is unreliable)
    if max_pe > 0.25:
        worst_dim = "POWER" if pe_power == max_pe else "FREQ" if pe_freq == max_pe else "AREA"
        return f"{worst_dim}_MODEL_UNRELIABLE"

    # 4. Behavioural fallbacks
    if lat > 0.65:
        return "SLOW_SUGGESTIONS"
    if conf < 0.50 and ppa_pass < 0.3:
        return "LOW_CONFIDENCE_FAILURES"
    if dominant_action == "reject":
        return "SYSTEMATIC_REJECTIONS"
    if dominant_action == "modify":
        return "REQUIRES_MODIFICATION"

    return f"MIXED_{dominant_fail}"


def cluster_sessions(
    records: List[Any],
    n_clusters: int = 4,
) -> ClusteringResult:
    """
    Cluster SuggestionRecord list into n_clusters groups using k-means.
    Returns ClusteringResult with per-cluster analysis.
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import silhouette_score as _silhouette
        import numpy as np
    except ImportError:
        raise ImportError("scikit-learn required: pip install scikit-learn")

    # Build feature matrix
    valid_records = []
    X_raw = []
    for r in records:
        v = _extract_vector(r)
        if v is not None:
            valid_records.append(r)
            X_raw.append(v)

    if len(X_raw) < n_clusters * 2:
        return ClusteringResult(
            n_clusters=0, clusters=[], inertia=float("nan"),
            silhouette_score=None, feature_names=FEATURE_NAMES,
            verdict="INSUFFICIENT_DATA",
        )

    X = np.array(X_raw)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    inertia = float(km.inertia_)

    # Silhouette (only if >1 cluster populated)
    unique_labels = set(labels)
    sil = None
    if len(unique_labels) > 1:
        try:
            sil = round(float(_silhouette(X_scaled, labels)), 4)
        except Exception:
            sil = None

    # Build per-cluster objects
    clusters: List[SessionCluster] = []
    for cid in range(n_clusters):
        member_idx = [i for i, lbl in enumerate(labels) if lbl == cid]
        if not member_idx:
            continue
        members = [valid_records[i] for i in member_idx]

        # Centroid in original feature space (not scaled)
        centroid_vec = X[member_idx].mean(axis=0)
        centroid = {name: round(float(v), 4) for name, v in zip(FEATURE_NAMES, centroid_vec)}

        # Dominant fail_mode
        fail_counts: Dict[str, int] = {}
        for r in members:
            fail_counts[r.fail_mode] = fail_counts.get(r.fail_mode, 0) + 1
        dominant_fail = max(fail_counts, key=fail_counts.get)

        # Dominant action
        act_counts: Dict[str, int] = {}
        for r in members:
            act_counts[r.action] = act_counts.get(r.action, 0) + 1
        dominant_action = max(act_counts, key=act_counts.get)

        # RTL kind distribution
        kind_counts: Dict[str, int] = {}
        for r in members:
            k = r.rtl_kind or "unknown"
            kind_counts[k] = kind_counts.get(k, 0) + 1

        mean_conf = float(np.mean([r.confidence for r in members if r.confidence is not None]))
        lat_vals = [r.latency_ms for r in members if r.latency_ms is not None]
        mean_lat = float(np.mean(lat_vals)) if lat_vals else None
        ppa_pass_rate = sum(1 for r in members if r.fail_mode == "PASS") / len(members)

        label = _auto_label(centroid, dominant_fail, dominant_action)

        clusters.append(SessionCluster(
            cluster_id=cid,
            label=label,
            n=len(members),
            member_session_ids=[r.session_id for r in members],
            centroid=centroid,
            dominant_fail_mode=dominant_fail,
            dominant_action=dominant_action,
            rtl_kinds=kind_counts,
            mean_confidence=round(mean_conf, 4),
            mean_latency_ms=round(mean_lat, 1) if mean_lat else None,
            ppa_pass_rate=round(ppa_pass_rate, 4),
        ))

    # Verdict based on silhouette
    if sil is None:
        verdict = "CLUSTERED_NO_SILHOUETTE"
    elif sil > 0.5:
        verdict = "WELL_SEPARATED_CLUSTERS"
    elif sil > 0.25:
        verdict = "MODERATE_SEPARATION"
    else:
        verdict = "OVERLAPPING_CLUSTERS"

    return ClusteringResult(
        n_clusters=len(clusters),
        clusters=clusters,
        inertia=round(inertia, 4),
        silhouette_score=sil,
        feature_names=FEATURE_NAMES,
        verdict=verdict,
    )


def format_clustering_report(result: ClusteringResult) -> str:
    lines = [
        "Session Clustering Analysis",
        "=" * 60,
        f"  Clusters found:    {result.n_clusters}",
        f"  Silhouette score:  {result.silhouette_score}  (>0.5 = well-separated)",
        f"  Inertia:           {result.inertia}",
        f"  Verdict:           {result.verdict}",
        "",
    ]
    for c in sorted(result.clusters, key=lambda x: -x.n):
        lines += [
            f"  Cluster {c.cluster_id}: [{c.label}]  (n={c.n})",
            f"    PPA pass rate:     {c.ppa_pass_rate:.1%}",
            f"    Mean confidence:   {c.mean_confidence:.3f}",
            f"    Mean latency:      {c.mean_latency_ms} ms",
            f"    Dominant fail:     {c.dominant_fail_mode}",
            f"    Dominant action:   {c.dominant_action}",
            f"    RTL kinds:         {c.rtl_kinds}",
            "",
        ]
    lines += [
        "  Interpretation: clusters with same label across runs → systematic copilot bias.",
        "  'AREA_BLOAT' + 'small_fsm' dominating → FSM rewrites inflate area → prompt fix.",
        "  'FREQ_MODEL_UNRELIABLE' → LLM doesn't understand timing → needs timing-aware training.",
    ]
    return "\n".join(lines)
