# scripts/debug_analyzer.py
from pathlib import Path
import json

def debug_analyzer():
    print("=== DEBUGGING SESSION ANALYSIS ===\n")
    
    # Read first session
    telemetry_dir = Path("data/telemetry/deep_sessions")
    sessions = list(telemetry_dir.glob("sess_*.jsonl"))
    
    if not sessions:
        print("No sessions found!")
        return
    
    first_session = sessions[0]
    print(f"Analyzing: {first_session.name}\n")
    
    # Read all events
    events = []
    with open(first_session) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    print(f"Total events in file: {len(events)}")
    
    # Check event types
    event_types = {}
    for e in events:
        evt_type = e.get("event_type", "unknown")
        event_types[evt_type] = event_types.get(evt_type, 0) + 1
    
    print("\nEvent types found:")
    for evt_type, count in event_types.items():
        print(f"  - {evt_type}: {count}")
    
    # Check for suggestion events
    print("\n=== SUGGESTION EVENTS ===")
    sug_events = [e for e in events if e.get("event_type") in ("suggestion_generated", "suggestion_shown")]
    print(f"Found {len(sug_events)} suggestion events")
    
    if sug_events:
        first_sug = sug_events[0]
        print("\nFirst suggestion fields:")
        for key, value in first_sug.items():
            print(f"  - {key}: {value}")

if __name__ == "__main__":
    debug_analyzer()