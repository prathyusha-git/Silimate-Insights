from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"

INPUT = REPORTS / "session_qa_results.csv"

OUT_BUCKETS = REPORTS / "session_buckets_summary.csv"
OUT_TOP_POWER = REPORTS / "ppa_failures_top10_power.csv"
OUT_TOP_FREQ = REPORTS / "ppa_failures_top10_freq.csv"
OUT_TOP_AREA = REPORTS / "ppa_failures_top10_area.csv"
OUT_CONF_MISMATCH = REPORTS / "confidence_mismatch_top10.csv"

def load_df(path: Path) -> pd.DataFrame:
    # Try UTF-8 first; fallback if Windows encoding got involved
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")

def ensure_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing {INPUT}. Run the session analyzer first.")

    df = load_df(INPUT)

    # Clean obvious encoding artifacts in text columns
    for c in ["root_cause_hypothesis", "action_reason"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.replace("â†’", "->", regex=False)

    # Numeric columns we will rank by
    df = ensure_numeric(df, [
        "confidence", "latency_ms",
        "target_power", "target_freq", "target_area",
        "base_power", "base_freq", "base_area",
        "actual_power", "actual_freq", "actual_area",
        "delta_power", "delta_freq", "delta_area",
    ])

    # --- 1) Bucket summary: fail_mode x action
    buckets = (
        df.groupby(["fail_mode", "action"], dropna=False)
          .size()
          .reset_index(name="count")
          .sort_values(["count"], ascending=False)
    )
    buckets.to_csv(OUT_BUCKETS, index=False, encoding="utf-8")
    print("Wrote:", OUT_BUCKETS)

    # Helper: only keep PPA failures
    ppa_fail = df[df["fail_mode"].astype(str).str.startswith("FAIL_", na=False)].copy()

    # --- 2) Top 10 POWER: biggest positive delta_power (power increased is bad)
    if "delta_power" in ppa_fail.columns:
        top_power = (
            ppa_fail.sort_values("delta_power", ascending=False)
                   .head(10)
        )
        top_power.to_csv(OUT_TOP_POWER, index=False, encoding="utf-8")
        print("Wrote:", OUT_TOP_POWER)

    # --- 3) Top 10 FREQ: treat freq shortfall as target - actual (positive means under target)
    if "target_freq" in ppa_fail.columns and "actual_freq" in ppa_fail.columns:
        ppa_fail["freq_shortfall"] = ppa_fail["target_freq"] - ppa_fail["actual_freq"]
        top_freq = (
            ppa_fail.sort_values("freq_shortfall", ascending=False)
                   .head(10)
        )
        top_freq.to_csv(OUT_TOP_FREQ, index=False, encoding="utf-8")
        print("Wrote:", OUT_TOP_FREQ)

    # --- 4) Top 10 AREA: biggest positive delta_area (area increased is bad)
    if "delta_area" in ppa_fail.columns:
        top_area = (
            ppa_fail.sort_values("delta_area", ascending=False)
                   .head(10)
        )
        top_area.to_csv(OUT_TOP_AREA, index=False, encoding="utf-8")
        print("Wrote:", OUT_TOP_AREA)

    # --- 5) Confidence mismatch: high confidence but action != accept
    # Only works if confidence is present (not all NaN)
    if "confidence" in df.columns and df["confidence"].notna().any():
        mismatch = df[df["action"].isin(["reject", "modify"])].copy()
        mismatch = mismatch.sort_values("confidence", ascending=False).head(10)
        mismatch.to_csv(OUT_CONF_MISMATCH, index=False, encoding="utf-8")
        print("Wrote:", OUT_CONF_MISMATCH)
    else:
        print("Skipped confidence mismatch: confidence column missing/empty.")

    print("\nDone. Check scripts/reports/ for output files.")

if __name__ == "__main__":
    main()
