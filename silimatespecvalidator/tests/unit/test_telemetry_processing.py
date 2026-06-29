# silimatespecvalidator/tests/unit/test_telemetry_processing.py

import pytest
import json
import tempfile
from pathlib import Path
from specvalidator.core.session_qa_analyzer import (
    _read_jsonl,
    _get_baseline,
    _get_eval_for_suggestion
)

class TestTelemetryProcessing:
    """Test telemetry data processing accuracy"""
    
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        import shutil
        shutil.rmtree(temp)
    
    def test_jsonl_parsing(self, temp_dir):
        """Test JSONL file parsing"""
        events = [
            {"event_type": "session_start", "session_id": "test_001"},
            {"event_type": "suggestion_generated", "suggestion_id": "sugg_001"},
            {"event_type": "action_taken", "action": "accept"}
        ]
        
        jsonl_file = temp_dir / "test.jsonl"
        with open(jsonl_file, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        parsed = _read_jsonl(jsonl_file)
        assert len(parsed) == 3
        assert parsed[0]["event_type"] == "session_start"
        assert parsed[1]["suggestion_id"] == "sugg_001"
        assert parsed[2]["action"] == "accept"
    
    def test_baseline_extraction(self):
        """Test extracting baseline from different event schemas"""
        # Test baseline_ppa schema
        events = [{
            "event_type": "baseline_ppa",
            "baseline_power": 100.0,
            "baseline_freq": 2000.0,
            "baseline_area": 10.0,
            "target_power": 90.0,
            "target_freq": 2100.0,
            "target_area": 9.0
        }]
        
        baseline = _get_baseline(events)
        assert baseline["base_power"] == 100.0
        assert baseline["base_freq"] == 2000.0
        assert baseline["base_area"] == 10.0
        assert baseline["target_power"] == 90.0
    
    def test_evaluation_result_extraction(self):
        """Test extracting evaluation results for specific suggestion"""
        events = [
            {"event_type": "evaluation_result", 
             "suggestion_id": "sugg_001",
             "actual_power": 95.0},
            {"event_type": "evaluation_result",
             "suggestion_id": "sugg_002", 
             "actual_power": 105.0},
            {"event_type": "evaluation_result",
             "suggestion_id": "sugg_001",
             "actual_power": 96.0}  # Later result should override
        ]
        
        result = _get_eval_for_suggestion(events, "sugg_001")
        assert result["actual_power"] == 96.0  # Should get last one
        
        result = _get_eval_for_suggestion(events, "sugg_002")
        assert result["actual_power"] == 105.0
        
        result = _get_eval_for_suggestion(events, "sugg_003")
        assert result is None
    
    def test_event_filtering(self):
        """Test filtering events by type"""
        events = [
            {"event_type": "session_start"},
            {"event_type": "suggestion_generated"},
            {"event_type": "suggestion_generated"},
            {"event_type": "action_taken"},
            {"event_type": "session_end"}
        ]
        
        suggestions = [e for e in events if e.get("event_type") == "suggestion_generated"]
        assert len(suggestions) == 2
        
        actions = [e for e in events if e.get("event_type") == "action_taken"]
        assert len(actions) == 1
    
    def test_session_id_consistency(self):
        """Test session ID tracking across events"""
        session_id = "sess_abc123"
        events = [
            {"event_type": "session_start", "session_id": session_id},
            {"event_type": "suggestion_generated", "session_id": session_id},
            {"event_type": "action_taken", "session_id": session_id}
        ]
        
        # All events should have same session ID
        session_ids = [e.get("session_id") for e in events]
        assert all(sid == session_id for sid in session_ids)
    
    def test_timestamp_parsing(self):
        """Test timestamp handling in telemetry"""
        from datetime import datetime
        
        timestamp = "2024-01-07T10:30:00Z"
        event = {"event_type": "test", "timestamp": timestamp}
        
        # Parse ISO format timestamp
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 7