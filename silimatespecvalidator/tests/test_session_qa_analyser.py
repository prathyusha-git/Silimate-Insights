# silimatespecvalidator/tests/test_session_qa_analyzer.py

import pytest
from pathlib import Path
import tempfile
import json
from specvalidator.core.session_qa_analyzer import (
    _read_jsonl,
    _get_baseline,
    _ppa_fail_mode,
    _action_alignment,
    _hypothesis_from_fail_and_features,
    _get_eval_for_suggestion,
    SuggestionRecord
)

class TestSessionAnalyzer:
    """Test session QA analysis functionality"""
    
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        import shutil
        shutil.rmtree(temp)
    
    def test_jsonl_reading(self, temp_dir):
        """Test reading JSONL telemetry files"""
        test_file = temp_dir / "test.jsonl"
        events = [
            {"event_type": "session_start", "session_id": "test_001"},
            {"event_type": "suggestion_generated", "suggestion_id": "sugg_001"}
        ]
        
        with open(test_file, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        loaded = _read_jsonl(test_file)
        assert len(loaded) == 2
        assert loaded[0]["session_id"] == "test_001"
    
    def test_baseline_extraction(self):
        """Test extracting baseline PPA from events"""
        events = [
            {"event_type": "baseline_ppa",
             "baseline_power": 100.5,
             "baseline_freq": 2000.0,
             "baseline_area": 10.2,
             "target_power": 95.0}
        ]
        
        baseline = _get_baseline(events)
        assert baseline is not None
        assert baseline["base_power"] == 100.5
        assert baseline["target_power"] == 95.0
    
    def test_ppa_fail_mode_detection(self):
        """Test PPA failure classification"""
        # Test PASS
        assert _ppa_fail_mode(100, 2000, 10, 95, 2100, 9) == "PASS"
        
        # Test single failures
        assert _ppa_fail_mode(100, 2000, 10, 105, 2100, 9) == "FAIL_POWER"
        assert _ppa_fail_mode(100, 2000, 10, 95, 1900, 9) == "FAIL_FREQ"
        assert _ppa_fail_mode(100, 2000, 10, 95, 2100, 11) == "FAIL_AREA"
        
        # Test multiple failures
        assert _ppa_fail_mode(100, 2000, 10, 105, 1900, 11) == "FAIL_POWER_FREQ_AREA"
        
        # Test with None
        assert _ppa_fail_mode(None, 2000, 10, 95, 2100, 9) == "UNKNOWN"
    
    def test_action_alignment_patterns(self):
        """Test suspicious pattern detection"""
        # Normal alignment
        assert _action_alignment("PASS", "accept") == "OK"
        assert _action_alignment("FAIL_POWER", "reject") == "OK"
        
        # Suspicious patterns
        assert _action_alignment("PASS", "reject") == "SUSPICIOUS_REJECT"
        assert _action_alignment("FAIL_AREA", "accept") == "RISKY_ACCEPT"
        
        # Unknown
        assert _action_alignment("UNKNOWN", "accept") == "UNKNOWN"
    
    def test_root_cause_hypothesis(self):
        """Test hypothesis generation from RTL features"""
        # Area failure due to bitwidth
        hyp = _hypothesis_from_fail_and_features(
            "FAIL_AREA",
            {"d_bitwidth_tokens": 5, "d_assign": 0, "d_mux_ternary": 0}
        )
        assert "wider bitwidths" in hyp
        
        # Frequency failure due to deep logic
        hyp = _hypothesis_from_fail_and_features(
            "FAIL_FREQ",
            {"d_max_ops_in_line": 3, "d_always_ff": 0, "d_bitwidth_tokens": 0}
        )
        assert "combinational logic" in hyp
        
        # Power failure due to operators
        hyp = _hypothesis_from_fail_and_features(
            "FAIL_POWER",
            {"d_op_xor": 2, "d_op_mul": 1, "d_always_ff": 0}
        )
        assert "switching-heavy" in hyp
        
        # Pass should return N/A
        hyp = _hypothesis_from_fail_and_features("PASS", {"d_assign": 1})
        assert hyp == "N/A"
    
    def test_suggestion_record_creation(self):
        """Test SuggestionRecord dataclass"""
        record = SuggestionRecord(
            session_id="sess_001",
            suggestion_id="sugg_001",
            action="accept",
            action_reason="meets_targets",
            confidence=0.85,
            latency_ms=1500,
            target_power=100.0,
            target_freq=2000.0,
            target_area=10.0,
            base_power=110.0,
            base_freq=1900.0,
            base_area=11.0,
            actual_power=95.0,
            actual_freq=2100.0,
            actual_area=9.5,
            delta_power=-15.0,
            delta_freq=200.0,
            delta_area=-1.5,
            fail_mode="PASS",
            action_alignment="OK",
            rtl_before_ref="before.sv",
            rtl_after_ref="after.sv",
            diff_ref="diff.patch",
            root_cause_hypothesis="N/A"
        )
        
        assert record.session_id == "sess_001"
        assert record.confidence == 0.85
        assert record.fail_mode == "PASS"