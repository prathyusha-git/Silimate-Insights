# scripts/run_session_qa.py
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent          # .../Silimate Insights/scripts
ROOT = SCRIPTS.parent                              # .../Silimate Insights
PKG_ROOT = ROOT / "silimatespecvalidator"          # contains specvalidator/

sys.path.insert(0, str(PKG_ROOT))

from specvalidator.core.session_qa_analyzer import analyze_all_sessions

if __name__ == "__main__":
    # Use the correct relative paths from scripts directory
    analyze_all_sessions(
        sessions_folder="data/telemetry/deep_sessions",    # ✅ Correct path
        artifacts_folder="artifacts/sessions",             # ✅ Correct path  
        out_folder="reports",                              # Output location
    )
    print(f"Done. See reports folder")