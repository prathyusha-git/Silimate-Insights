# silimatespecvalidator/tests/performance/test_memory.py

import pytest
import psutil
import gc
import tracemalloc
from pathlib import Path
import tempfile

class TestMemoryOptimization:
    """Test memory usage and optimization"""
    
    @pytest.mark.performance
    def test_memory_efficient_file_processing(self):
        """Test memory-efficient large file processing"""
        tracemalloc.start()
        
        with tempfile.TemporaryDirectory() as temp:
            # Create large JSONL file (10MB)
            large_file = Path(temp) / "large.jsonl"
            with open(large_file, 'w') as f:
                for i in range(100000):
                    f.write(f'{{"event": "test", "id": {i}, "data": "x" * 100}}\n')
            
            # Memory before
            snapshot1 = tracemalloc.take_snapshot()
            
            # Process file line by line (memory efficient)
            events = []
            with open(large_file) as f:
                for line in f:
                    if len(events) < 1000:  # Keep only recent events
                        events.append(line)
                    else:
                        events.pop(0)
                        events.append(line)
            
            # Memory after
            snapshot2 = tracemalloc.take_snapshot()
            top_stats = snapshot2.compare_to(snapshot1, 'lineno')
            
            # Calculate memory increase
            total_increase = sum(stat.size_diff for stat in top_stats) / 1024 / 1024  # MB
            
            # Should use less than 10MB for 10MB file (streaming)
            assert total_increase < 10, f"Memory increased by {total_increase:.2f}MB"
        
        tracemalloc.stop()
    
    @pytest.mark.performance
    def test_memory_leak_detection(self):
        """Test for memory leaks in repeated operations"""
        import gc
        
        def get_memory_usage():
            """Get current memory usage in MB"""
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        
        # Initial memory
        gc.collect()
        initial_memory = get_memory_usage()
        
        # Perform repeated operations
        for iteration in range(100):
            # Simulate session processing
            data = {
                "session_id": f"mem_test_{iteration}",
                "events": [{"type": "test", "data": "x" * 1000} for _ in range(100)]
            }
            # Process and discard
            _ = len(data["events"])
            del data
        
        # Force garbage collection
        gc.collect()
        final_memory = get_memory_usage()
        
        # Memory increase should be minimal
        memory_increase = final_memory - initial_memory
        assert memory_increase < 50, f"Memory increased by {memory_increase:.2f}MB (potential leak)"
    
    @pytest.mark.performance
    def test_lazy_loading_optimization(self):
        """Test lazy loading of large datasets"""
        
        class LazyDataLoader:
            """Lazy loader for session data"""
            def __init__(self, session_dir):
                self.session_dir = Path(session_dir)
                self._cache = {}
            
            def get_session(self, session_id):
                if session_id not in self._cache:
                    # Load only when needed
                    session_file = self.session_dir / f"{session_id}.jsonl"
                    if session_file.exists():
                        with open(session_file) as f:
                            self._cache[session_id] = [line.strip() for line in f]
                return self._cache.get(session_id, [])
            
            def clear_cache(self):
                self._cache.clear()
                gc.collect()
        
        with tempfile.TemporaryDirectory() as temp:
            # Create test sessions
            for i in range(50):
                session_file = Path(temp) / f"session_{i:03d}.jsonl"
                session_file.write_text(f'{{"id": {i}}}\n' * 100)
            
            loader = LazyDataLoader(temp)
            
            # Memory before loading
            gc.collect()
            mem_before = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Access only a few sessions
            _ = loader.get_session("session_001")
            _ = loader.get_session("session_005")
            _ = loader.get_session("session_010")
            
            # Memory after selective loading
            mem_after = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Should use minimal memory (only 3 sessions loaded)
            memory_used = mem_after - mem_before
            assert memory_used < 10, f"Used {memory_used:.2f}MB for 3 sessions"
            
            # Test cache clearing
            loader.clear_cache()
            gc.collect()
            mem_cleared = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Memory should be released
            assert mem_cleared <= mem_after
    
    @pytest.mark.performance
    def test_batch_processing_memory(self):
        """Test memory-efficient batch processing"""
        
        def process_in_batches(items, batch_size=100):
            """Process items in batches to limit memory"""
            results = []
            batch = []
            
            for item in items:
                batch.append(item)
                if len(batch) >= batch_size:
                    # Process batch
                    batch_result = sum(x["value"] for x in batch)
                    results.append(batch_result)
                    batch.clear()  # Clear batch to free memory
            
            # Process remaining
            if batch:
                results.append(sum(x["value"] for x in batch))
            
            return results
        
        # Large dataset
        large_dataset = [{"id": i, "value": i} for i in range(10000)]
        
        # Track memory during processing
        gc.collect()
        mem_start = psutil.Process().memory_info().rss / 1024 / 1024
        
        results = process_in_batches(large_dataset, batch_size=100)
        
        mem_end = psutil.Process().memory_info().rss / 1024 / 1024
        memory_used = mem_end - mem_start
        
        assert len(results) == 100  # 10000 items / 100 batch size
        assert memory_used < 20, f"Batch processing used {memory_used:.2f}MB"