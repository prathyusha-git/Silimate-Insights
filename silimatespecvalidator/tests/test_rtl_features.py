# silimatespecvalidator/tests/test_rtl_features.py

import pytest
from pathlib import Path
import tempfile
from specvalidator.core.rtl_features import extract_features, diff_features

class TestRTLFeatures:
    """Test RTL feature extraction and analysis"""
    
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        import shutil
        shutil.rmtree(temp)
    
    def test_feature_extraction(self, temp_dir):
        """Test extracting features from RTL"""
        rtl_content = """module test(input a, b, c, output y);
        assign y = a & b | c;
        always_ff @(posedge clk) begin
            q <= d;
        end
        assign z = a ^ b;
        endmodule"""
        
        rtl_file = temp_dir / "test.sv"
        rtl_file.write_text(rtl_content)
        
        features = extract_features(str(rtl_file))
        
        assert features["lines"] == 7
        assert features["assign"] == 2
        assert features["always_ff"] == 1
        assert features["op_xor"] == 1
    
    def test_operator_counting(self, temp_dir):
        """Test counting specific operators"""
        rtl_content = """module alu();
        assign result = a * b + c ^ d;
        assign flag = (a > b) ? 1'b1 : 1'b0;
        endmodule"""
        
        rtl_file = temp_dir / "alu.sv"
        rtl_file.write_text(rtl_content)
        
        features = extract_features(str(rtl_file))
        
        assert features["op_mul"] == 1
        assert features["op_add"] == 1
        assert features["op_xor"] == 1
        assert features["mux_ternary"] == 1
    
    def test_feature_diff(self):
        """Test calculating feature deltas"""
        before = {
            "lines": 10,
            "assign": 2,
            "always_ff": 1,
            "op_mul": 0
        }
        after = {
            "lines": 15,
            "assign": 4,
            "always_ff": 2,
            "op_mul": 2
        }
        
        delta = diff_features(before, after)
        
        assert delta["d_lines"] == 5
        assert delta["d_assign"] == 2
        assert delta["d_always_ff"] == 1
        assert delta["d_op_mul"] == 2