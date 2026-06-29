# silimatespecvalidator/tests/performance/test_parallel.py

import pytest
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
import tempfile

class TestParallelExecution:
    """Test parallel processing capabilities"""
    
    @pytest.mark.performance
    def test_parallel_rtl_validation(self):
        """Test parallel RTL validation across multiple files"""
        from specvalidator.eda_integration.iverilog import lint_rtl
        
        # Create test RTL files
        with tempfile.TemporaryDirectory() as temp:
            rtl_files = []
            for i in range(20):
                rtl_file = Path(temp) / f"module_{i}.sv"
                rtl_file.write_text(f"module m{i}(); endmodule")
                rtl_files.append(str(rtl_file))
            
            # Sequential execution
            start_seq = time.perf_counter()
            seq_results = []
            for rtl in rtl_files:
                result = lint_rtl(rtl)
                seq_results.append(result)
            seq_time = time.perf_counter() - start_seq
            
            # Parallel execution
            start_par = time.perf_counter()
            with ThreadPoolExecutor(max_workers=4) as executor:
                par_results = list(executor.map(lint_rtl, rtl_files))
            par_time = time.perf_counter() - start_par
            
            # Verify speedup
            speedup = seq_time / par_time
            assert speedup > 1.5, f"Parallel speedup only {speedup:.2f}x"
            
            # Verify results consistency
            assert len(seq_results) == len(par_results)
            assert all(r["ok"] for r in par_results)
    
    @pytest.mark.performance
    def test_parallel_session_analysis(self):
        """Test parallel analysis of multiple sessions"""
        from specvalidator.core.session_qa_analyzer import _read_jsonl, _get_baseline
        
        def analyze_session(session_data):
            """Worker function for parallel processing"""
            events = session_data["events"]
            baseline = _get_baseline(events)
            return {
                "session_id": session_data["id"],
                "has_baseline": baseline is not None
            }
        
        # Create test data
        sessions = []
        for i in range(30):
            sessions.append({
                "id": f"parallel_sess_{i}",
                "events": [
                    {"event_type": "session_start", "session_id": f"parallel_sess_{i}"},
                    {"event_type": "baseline_ppa", "baseline_power": 100 + i}
                ]
            })
        
        # Parallel processing with different worker counts
        for n_workers in [1, 2, 4, 8]:
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                results = list(executor.map(analyze_session, sessions))
            elapsed = time.perf_counter() - start
            
            # Verify all sessions processed
            assert len(results) == 30
            assert all(r["has_baseline"] for r in results)
            
            # Track performance
            print(f"Workers: {n_workers}, Time: {elapsed:.3f}s")
    
    @pytest.mark.performance
    def test_parallel_equivalence_checking(self):
        """Test parallel equivalence checking"""
        from specvalidator.eda_integration.iverilog import run_simulation
        
        def check_equivalence(test_case):
            """Check equivalence for given inputs"""
            inputs = test_case["inputs"]
            expected = test_case["expected"]
            # Mock simulation for performance testing
            result = sum(inputs.values()) % 2  # Simple mock
            return result == expected
        
        # Generate test cases
        test_cases = []
        for i in range(100):
            test_cases.append({
                "inputs": {"a": i % 2, "b": (i // 2) % 2},
                "expected": (i % 2 + (i // 2) % 2) % 2
            })
        
        # Sequential
        start_seq = time.perf_counter()
        seq_results = [check_equivalence(tc) for tc in test_cases]
        seq_time = time.perf_counter() - start_seq
        
        # Parallel
        start_par = time.perf_counter()
        with ProcessPoolExecutor(max_workers=4) as executor:
            par_results = list(executor.map(check_equivalence, test_cases))
        par_time = time.perf_counter() - start_par
        
        # Verify results match
        assert seq_results == par_results
        
        # Verify speedup for CPU-bound work
        speedup = seq_time / par_time
        print(f"Equivalence checking speedup: {speedup:.2f}x")
    
    @pytest.mark.performance 
    def test_parallel_report_generation(self):
        """Test parallel generation of multiple report types"""
        import json
        import csv
        from io import StringIO
        
        def generate_report(report_type, data):
            """Generate report of specified type"""
            if report_type == "json":
                return json.dumps(data, indent=2)
            elif report_type == "csv":
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
                return output.getvalue()
            elif report_type == "summary":
                return f"Total records: {len(data)}\n"
        
        # Test data
        data = [{"id": i, "value": i * 10} for i in range(100)]
        report_types = ["json", "csv", "summary"] * 10  # 30 reports
        
        # Parallel report generation
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(generate_report, rt, data) for rt in report_types]
            reports = [f.result() for f in futures]
        elapsed = time.perf_counter() - start
        
        assert len(reports) == 30
        assert all(r is not None for r in reports)
        assert elapsed < 1.0, f"Report generation took {elapsed:.2f}s"