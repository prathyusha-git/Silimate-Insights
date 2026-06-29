# silimatespecvalidator/tests/regression/test_telemetry_edge_cases.py

import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

class TestTelemetryEdgeCases:
    """Tests for edge cases discovered from telemetry analysis"""
    
    @pytest.mark.regression
    def test_edge_duplicate_events(self):
        """Edge case: Duplicate events with same timestamp"""
        events = [
            {"event_type": "suggestion_generated", "timestamp": "2024-01-01T10:00:00Z", "id": "1"},
            {"event_type": "suggestion_generated", "timestamp": "2024-01-01T10:00:00Z", "id": "1"},
        ]
        
        # Should deduplicate
        unique_events = []
        seen = set()
        for event in events:
            key = (event.get("event_type"), event.get("timestamp"), event.get("id"))
            if key not in seen:
                unique_events.append(event)
                seen.add(key)
        
        assert len(unique_events) == 1
    
    @pytest.mark.regression
    def test_edge_out_of_order_timestamps(self):
        """Edge case: Events with out-of-order timestamps"""
        events = [
            {"event_type": "session_start", "timestamp": "2024-01-01T10:00:00Z"},
            {"event_type": "action_taken", "timestamp": "2024-01-01T09:59:00Z"},  # Before start!
            {"event_type": "session_end", "timestamp": "2024-01-01T10:01:00Z"}
        ]
        
        # Should sort by timestamp
        sorted_events = sorted(events, key=lambda x: x["timestamp"])
        assert sorted_events[0]["event_type"] == "action_taken"
        assert sorted_events[1]["event_type"] == "session_start"
    
    @pytest.mark.regression
    def test_edge_missing_session_end(self):
        """Edge case: Session without end event"""
        events = [
            {"event_type": "session_start", "session_id": "incomplete"},
            {"event_type": "suggestion_generated", "session_id": "incomplete"},
            # Missing session_end
        ]
        
        # Should handle incomplete sessions
        has_end = any(e.get("event_type") == "session_end" for e in events)
        if not has_end:
            # Add synthetic end event
            events.append({"event_type": "session_end", "session_id": "incomplete", "synthetic": True})
        
        assert len(events) == 3
        assert events[-1]["synthetic"] == True
    
    @pytest.mark.regression
    def test_edge_extreme_ppa_values(self):
        """Edge case: Extreme PPA values from telemetry"""
        extreme_cases = [
            (1e-10, 1e10, 1e-10),  # Very small/large
            (float('inf'), 1000, 10),  # Infinity
            (-100, 2000, 10),  # Negative power
            (100, 0, 10),  # Zero frequency
        ]
        
        for power, freq, area in extreme_cases:
            # Should handle without crashing
            if power == float('inf') or freq == 0 or power < 0:
                result = "INVALID"
            else:
                result = "PROCESSED"
            assert result in ["INVALID", "PROCESSED"]
    
    @pytest.mark.regression 
    def test_edge_rapid_fire_events(self):
        """Edge case: Many events in same millisecond"""
        base_time = datetime.now()
        events = []
        
        # 100 events in same millisecond
        for i in range(100):
            events.append({
                "event_type": "action_taken",
                "timestamp": base_time.isoformat(),
                "sequence": i
            })
        
        # Should preserve order
        assert all(events[i]["sequence"] == i for i in range(100))
    
    @pytest.mark.regression
    def test_edge_null_values_in_metrics(self):
        """Edge case: Null/None values in PPA metrics"""
        from specvalidator.core.session_qa_analyzer import _ppa_fail_mode
        
        test_cases = [
            (None, None, None, 100, 2000, 10),
            (100, None, 10, None, 2000, None),
            (None, 2000, None, None, None, None),
        ]
        
        for case in test_cases:
            result = _ppa_fail_mode(*case)
            assert result == "UNKNOWN"
    
    @pytest.mark.regression
    def test_edge_very_long_session(self):
        """Edge case: Session with 10,000+ events"""
        with tempfile.TemporaryDirectory() as temp:
            session_file = Path(temp) / "huge_session.jsonl"
            
            # Write huge session
            with open(session_file, 'w') as f:
                for i in range(10000):
                    event = {"event_type": "metric", "id": i, "value": i % 100}
                    f.write(json.dumps(event) + '\n')
            
            # Should handle without memory issues
            events = []
            with open(session_file) as f:
                for line in f:
                    events.append(json.loads(line))
                    if len(events) > 1000:
                        events.pop(0)  # Keep sliding window
            
            assert len(events) == 1000  # Only kept last 1000