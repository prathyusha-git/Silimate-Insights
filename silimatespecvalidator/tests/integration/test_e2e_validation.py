# silimatespecvalidator/tests/integration/test_e2e_validation.py

import pytest
import json
from pathlib import Path
import tempfile
from specvalidator.core.session_qa_analyzer import analyze_all_sessions

class TestEndToEndValidation:
    """Test complete suggestion validation workflows"""
    
    @pytest.fixture
    def test_environment(self):
        """Set up complete test environment"""
        temp = tempfile.mkdtemp()
        base = Path(temp)
        
        # Create directory structure
        telemetry_dir = base / "telemetry"
        artifacts_dir = base / "artifacts"
        reports_dir = base / "reports"
        
        telemetry_dir.mkdir()
        artifacts_dir.mkdir()
        reports_dir.mkdir()
        
        yield {
            "base": base,
            "telemetry": telemetry_dir,
            "artifacts": artifacts_dir,
            "reports": reports_dir
        }
        
        import shutil
        shutil.rmtree(temp)
    
    def test_complete_suggestion_validation(self, test_environment):
        """Test validating a suggestion from telemetry to report"""
        # Create session data
        session_id = "e2e_test_session"
        suggestion_id = "e2e_test_suggestion"
        
        # Create RTL artifacts
        session_artifacts = test_environment["artifacts"] / session_id
        session_artifacts.mkdir()
        
        rtl_before = session_artifacts / "rtl_before.sv"
        rtl_after = session_artifacts / "rtl_after_sugg_1.sv"
        
        rtl_before.write_text("module test(); assign y = 0; endmodule")
        rtl_after.write_text("module test(); assign y = 1; assign z = 2; endmodule")
        
        # Create telemetry
        events = [
            {"event_type": "session_start", "session_id": session_id},
            {
                "event_type": "baseline_ppa",
                "session_id": session_id,
                "baseline_power": 100,
                "baseline_freq": 2000,
                "baseline_area": 10,
                "target_power": 90,
                "target_freq": 2100,
                "target_area": 9
            },
            {
                "event_type": "suggestion_generated",
                "session_id": session_id,
                "suggestion_id": suggestion_id,
                "confidence_score": 0.85,
                "latency_ms": 1500
            },
            {
                "event_type": "evaluation_result",
                "session_id": session_id,
                "suggestion_id": suggestion_id,
                "actual_power": 88,
                "actual_freq": 2150,
                "actual_area": 8.5
            },
            {
                "event_type": "action_taken",
                "session_id": session_id,
                "suggestion_id": suggestion_id,
                "action": "accept",
                "action_reason": "meets_targets"
            }
        ]
        
        jsonl_file = test_environment["telemetry"] / f"{session_id}.jsonl"
        with open(jsonl_file, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        # Run analysis
        records = analyze_all_sessions(
            sessions_folder=test_environment["telemetry"],
            artifacts_folder=test_environment["artifacts"],
            out_folder=test_environment["reports"]
        )
        
        # Validate results
        assert len(records) == 1
        record = records[0]
        
        assert record.session_id == session_id
        assert record.suggestion_id == suggestion_id
        assert record.confidence == 0.85
        assert record.action == "accept"
        assert record.fail_mode == "PASS"
        assert record.action_alignment == "OK"
        
        # Check report files exist
        csv_file = test_environment["reports"] / "session_qa_results.csv"
        json_file = test_environment["reports"] / "session_qa_results.json"
        summary_file = test_environment["reports"] / "session_qa_summary.txt"
        
        assert csv_file.exists()
        assert json_file.exists()
        assert summary_file.exists()
    
    def test_multi_session_analysis(self, test_environment):
        """Test analyzing multiple sessions"""
        sessions = ["sess_001", "sess_002", "sess_003"]
        
        for session_id in sessions:
            # Create minimal artifacts
            session_artifacts = test_environment["artifacts"] / session_id
            session_artifacts.mkdir()
            (session_artifacts / "rtl_before.sv").write_text("module m(); endmodule")
            (session_artifacts / "rtl_after_sugg_1.sv").write_text("module m(); assign y=1; endmodule")
            
            # Create telemetry
            events = [
                {"event_type": "session_start", "session_id": session_id},
                {"event_type": "baseline_ppa", "session_id": session_id,
                 "baseline_power": 100, "baseline_freq": 2000, "baseline_area": 10,
                 "target_power": 90, "target_freq": 2100, "target_area": 9},
                {"event_type": "suggestion_generated", "session_id": session_id,
                 "suggestion_id": f"sugg_{session_id}", "confidence_score": 0.8},
                {"event_type": "evaluation_result", "session_id": session_id,
                 "suggestion_id": f"sugg_{session_id}",
                 "actual_power": 85, "actual_freq": 2200, "actual_area": 8},
                {"event_type": "action_taken", "session_id": session_id,
                 "suggestion_id": f"sugg_{session_id}", "action": "accept"}
            ]
            
            jsonl_file = test_environment["telemetry"] / f"{session_id}.jsonl"
            with open(jsonl_file, 'w') as f:
                for event in events:
                    f.write(json.dumps(event) + '\n')
        
        # Analyze all sessions
        records = analyze_all_sessions(
            sessions_folder=test_environment["telemetry"],
            artifacts_folder=test_environment["artifacts"],
            out_folder=test_environment["reports"]
        )
        
        assert len(records) == 3
        assert all(r.confidence == 0.8 for r in records)
        assert all(r.fail_mode == "PASS" for r in records)
    
    def test_suspicious_pattern_detection(self, test_environment):
        """Test detection of suspicious user behavior"""
        session_id = "suspicious_session"
        
        # Create artifacts
        session_artifacts = test_environment["artifacts"] / session_id
        session_artifacts.mkdir()
        (session_artifacts / "rtl_before.sv").write_text("module m(); endmodule")
        (session_artifacts / "rtl_after_sugg_1.sv").write_text("module m(); assign y=1; endmodule")
        
        # Create telemetry with suspicious pattern (reject despite PASS)
        events = [
            {"event_type": "session_start", "session_id": session_id},
            {"event_type": "baseline_ppa", "session_id": session_id,
             "baseline_power": 100, "baseline_freq": 2000, "baseline_area": 10,
             "target_power": 90, "target_freq": 2100, "target_area": 9},
            {"event_type": "suggestion_generated", "session_id": session_id,
             "suggestion_id": "sugg_sus", "confidence_score": 0.9},
            {"event_type": "evaluation_result", "session_id": session_id,
             "suggestion_id": "sugg_sus",
             "actual_power": 85, "actual_freq": 2200, "actual_area": 8},  # Meets all targets
            {"event_type": "action_taken", "session_id": session_id,
             "suggestion_id": "sugg_sus", 
             "action": "reject",  # But user rejects!
             "action_reason": "unknown"}
        ]
        
        jsonl_file = test_environment["telemetry"] / f"{session_id}.jsonl"
        with open(jsonl_file, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        records = analyze_all_sessions(
            sessions_folder=test_environment["telemetry"],
            artifacts_folder=test_environment["artifacts"],
            out_folder=test_environment["reports"]
        )
        
        assert len(records) == 1
        assert records[0].fail_mode == "PASS"
        assert records[0].action == "reject"
        assert records[0].action_alignment == "SUSPICIOUS_REJECT"  # Detected!
        