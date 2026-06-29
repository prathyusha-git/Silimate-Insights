# silimatespecvalidator/tests/performance/test_latency.py

import pytest
import time
import concurrent.futures
from pathlib import Path
import tempfile
import json
from specvalidator.core.session_qa_analyzer import analyze_all_sessions
from specvalidator.core.rtl_features import extract_features

class TestLatencyPerformance:
    """Test system latency under various load conditions"""
    
    @pytest.fixture
    def performance_workspace(self):
        """Create workspace for performance testing"""
        temp = tempfile.mkdtemp()
        workspace = Path(temp)
        (workspace / "telemetry").mkdir()
        (workspace / "artifacts").mkdir()
        (workspace / "reports").mkdir()
        yield workspace
        import shutil
        shutil.rmtree(temp)
    
    @pytest.mark.performance
    def test_single_session_latency(self, performance_workspace):
        """Test latency for processing single session"""
        # Create minimal test data
        session_id = "perf_test_001"
        self._create_test_session(performance_workspace, session_id)
        
        # Measure processing time
        start = time.perf_counter()
        records = analyze_all_sessions(
            sessions_folder=performance_workspace / "telemetry",
            artifacts_folder=performance_workspace / "artifacts",
            out_folder=performance_workspace / "reports"
        )
        end = time.perf_counter()
        
        latency_ms = (end - start) * 1000
        
        # Assert reasonable latency (< 100ms for single session)
        assert latency_ms < 100, f"Single session took {latency_ms:.2f}ms"
        assert len(records) == 1
    
    @pytest.mark.performance
    def test_bulk_session_latency(self, performance_workspace):
        """Test latency for bulk session processing"""
        n_sessions = 50
        
        # Create test sessions
        for i in range(n_sessions):
            self._create_test_session(performance_workspace, f"bulk_sess_{i:03d}")
        
        # Measure bulk processing
        start = time.perf_counter()
        records = analyze_all_sessions(
            sessions_folder=performance_workspace / "telemetry",
            artifacts_folder=performance_workspace / "artifacts",
            out_folder=performance_workspace / "reports"
        )
        end = time.perf_counter()
        
        total_time = end - start
        avg_time_per_session = total_time / n_sessions * 1000
        
        # Assert reasonable average time (< 20ms per session)
        assert avg_time_per_session < 20, f"Average {avg_time_per_session:.2f}ms per session"
        assert len(records) == n_sessions
    
    @pytest.mark.performance
    def test_rtl_parsing_latency(self, performance_workspace):
        """Test RTL feature extraction latency"""
        # Create RTL files of varying sizes
        rtl_sizes = [
            ("small", 50),    # 50 lines
            ("medium", 500),  # 500 lines
            ("large", 2000)   # 2000 lines
        ]
        
        results = {}
        
        for size_name, n_lines in rtl_sizes:
            rtl_file = performance_workspace / f"test_{size_name}.sv"
            rtl_content = self._generate_rtl_content(n_lines)
            rtl_file.write_text(rtl_content)
            
            # Measure parsing time
            start = time.perf_counter()
            features = extract_features(str(rtl_file))
            end = time.perf_counter()
            
            latency_ms = (end - start) * 1000
            results[size_name] = late