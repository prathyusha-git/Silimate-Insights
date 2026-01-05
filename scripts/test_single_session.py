# scripts/test_single_session.py
import sys
from pathlib import Path
import json

# Add package to path
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
PKG_ROOT = ROOT / "silimatespecvalidator"
sys.path.insert(0, str(PKG_ROOT))

from specvalidator.core.rtl_features import extract_features, diff_features

def test_single_session():
    # Read first session
    telemetry_file = Path("data/telemetry/deep_sessions/sess_037a61e4.jsonl")
    
    events = []
    with open(telemetry_file) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    # Find suggestion event
    sug_event = None
    for e in events:
        if e.get("event_type") == "suggestion_generated":
            sug_event = e
            break
    
    if not sug_event:
        print("No suggestion found!")
        return
    
    print("Suggestion ID:", sug_event.get("suggestion_id"))
    print("Confidence:", sug_event.get("confidence_score"))
    
    # Test RTL paths
    session_id = sug_event.get("session_id")
    artifacts_dir = Path("artifacts/sessions") / session_id
    
    rtl_before = artifacts_dir / "rtl_before.sv"
    rtl_after = artifacts_dir / "rtl_after_sugg_1.sv"
    
    print(f"\nChecking RTL files:")
    print(f"  Before: {rtl_before} - Exists: {rtl_before.exists()}")
    print(f"  After: {rtl_after} - Exists: {rtl_after.exists()}")
    
    if rtl_before.exists() and rtl_after.exists():
        # Test feature extraction
        features_before = extract_features(str(rtl_before))
        features_after = extract_features(str(rtl_after))
        deltas = diff_features(features_before, features_after)
        
        print("\nFeature deltas:")
        for key, value in deltas.items():
            if value != 0:
                print(f"  {key}: {value}")
        
        print("\n✅ Everything works! The analyzer should process this session.")
    else:
        print("\n❌ RTL files not found - this is why analyzer gets 0 records!")

if __name__ == "__main__":
    test_single_session()