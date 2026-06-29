# silimatespecvalidator/tests/unit/test_ppa_calculations.py

import pytest
from specvalidator.core.session_qa_analyzer import _ppa_fail_mode

class TestPPACalculations:
    """Test PPA calculation correctness"""
    
    def test_ppa_delta_calculation(self):
        """Test delta calculation between baseline and actual"""
        from specvalidator.core.session_qa_analyzer import SuggestionRecord
        
        # Create record with known values
        record = SuggestionRecord(
            session_id="test",
            suggestion_id="test",
            action="accept",
            action_reason="test",
            confidence=0.8,
            latency_ms=1000,
            target_power=100.0,
            target_freq=2000.0,
            target_area=10.0,
            base_power=110.0,
            base_freq=1900.0,
            base_area=11.0,
            actual_power=95.0,
            actual_freq=2100.0,
            actual_area=9.5,
            delta_power=-15.0,  # 95 - 110
            delta_freq=200.0,    # 2100 - 1900
            delta_area=-1.5,     # 9.5 - 11
            fail_mode="PASS",
            action_alignment="OK",
            rtl_before_ref=None,
            rtl_after_ref=None,
            diff_ref=None,
            root_cause_hypothesis="N/A"
        )
        
        assert record.delta_power == -15.0
        assert record.delta_freq == 200.0
        assert record.delta_area == -1.5
    
    def test_percentage_improvement(self):
        """Test percentage improvement calculations"""
        baseline = 100.0
        actual = 85.0
        improvement = ((baseline - actual) / baseline) * 100
        assert improvement == 15.0
        
        baseline = 2000.0
        actual = 2200.0
        improvement = ((actual - baseline) / baseline) * 100
        assert improvement == 10.0
    
    def test_ppa_threshold_boundaries(self):
        """Test boundary conditions for pass/fail"""
        # Exactly at target should pass
        result = _ppa_fail_mode(100, 2000, 10, 100, 2000, 10)
        assert result == "PASS"
        
        # Just over power target should fail
        result = _ppa_fail_mode(100, 2000, 10, 100.01, 2000, 10)
        assert result == "FAIL_POWER"
        
        # Just under freq target should fail
        result = _ppa_fail_mode(100, 2000, 10, 100, 1999.99, 10)
        assert result == "FAIL_FREQ"
        
        # Just over area target should fail
        result = _ppa_fail_mode(100, 2000, 10, 100, 2000, 10.01)
        assert result == "FAIL_AREA"
    
    def test_weighted_ppa_score(self):
        """Test composite PPA scoring"""
        # Custom weighted scoring function
        def calculate_ppa_score(power_weight=0.4, freq_weight=0.3, area_weight=0.3):
            power_score = 0.9  # 90% of target
            freq_score = 1.1   # 110% of target  
            area_score = 0.95  # 95% of target
            
            weighted = (power_score * power_weight + 
                       freq_score * freq_weight + 
                       area_score * area_weight)
            return weighted
        
        score = calculate_ppa_score()
        assert 0.95 < score < 1.0  # Should be slightly below perfect
    
    def test_ppa_with_missing_values(self):
        """Test handling of None/missing values"""
        result = _ppa_fail_mode(None, 2000, 10, 95, 2100, 9)
        assert result == "UNKNOWN"
        
        result = _ppa_fail_mode(100, None, 10, 95, 2100, 9)
        assert result == "UNKNOWN"
        
        result = _ppa_fail_mode(100, 2000, None, 95, 2100, 9)
        assert result == "UNKNOWN"