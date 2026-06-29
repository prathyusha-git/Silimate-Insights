# silimatespecvalidator/tests/unit/test_rtl_parsing.py

import pytest
from pathlib import Path
import tempfile
from specvalidator.core.rtl_features import extract_features, diff_features

class TestRTLParsing:
    """Test RTL parsing and feature extraction accuracy"""
    
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield Path(temp)
        import shutil
        shutil.rmtree(temp)
    
    def test_parse_simple_module(self, temp_dir):
        """Test parsing basic SystemVerilog module"""
        rtl = """module simple(input a, b, output y);
            assign y = a & b;
        endmodule"""
        
        rtl_file = temp_dir / "simple.sv"
        rtl_file.write_text(rtl)
        
        features = extract_features(str(rtl_file))
        assert features["lines"] == 3
        assert features["assign"] == 1
    
    def test_parse_always_blocks(self, temp_dir):
        """Test detection of always blocks"""
        rtl = """module fsm();
            always_ff @(posedge clk) state <= next_state;
            always_comb begin
                next_state = state;
            end
        endmodule"""
        
        rtl_file = temp_dir / "fsm.sv"
        rtl_file.write_text(rtl)
        
        features = extract_features(str(rtl_file))
        assert features["always_ff"] == 1
        assert features["always_comb"] == 1
    
    def test_parse_operators(self, temp_dir):
        """Test operator counting accuracy"""
        rtl = """module alu();
            assign sum = a + b + c;
            assign product = x * y * z;
            assign xor_out = p ^ q ^ r;
        endmodule"""
        
        rtl_file = temp_dir / "alu.sv"
        rtl_file.write_text(rtl)
        
        features = extract_features(str(rtl_file))
        assert features["op_add"] == 2
        assert features["op_mul"] == 2
        assert features["op_xor"] == 2
    
    def test_parse_mux_detection(self, temp_dir):
        """Test ternary mux detection"""
        rtl = """module mux();
            assign y = sel ? a : b;
            assign z = (en == 1'b1) ? data : 8'h00;
        endmodule"""
        
        rtl_file = temp_dir / "mux.sv"
        rtl_file.write_text(rtl)
        
        features = extract_features(str(rtl_file))
        assert features["mux_ternary"] == 2
    
    def test_parse_bitwidth_tokens(self, temp_dir):
        """Test bitwidth declaration detection"""
        rtl = """module bus(
            input [31:0] data_in,
            output [7:0] byte_out,
            output [15:0] word_out
        );
        endmodule"""
        
        rtl_file = temp_dir / "bus.sv"
        rtl_file.write_text(rtl)
        
        features = extract_features(str(rtl_file))
        assert features["bitwidth_tokens"] == 3
    
    def test_parse_complex_expressions(self, temp_dir):
        """Test max operations per line metric"""
        rtl = """module complex();
            assign y = a + b - c * d / e;  // 4 ops
            assign z = x & y | z;           // 2 ops
        endmodule"""
        
        rtl_file = temp_dir / "complex.sv"
        rtl_file.write_text(rtl)
        
        features = extract_features(str(rtl_file))
        assert features["max_ops_in_line"] == 4
    
    def test_parse_empty_module(self, temp_dir):
        """Test parsing edge case - empty module"""
        rtl = "module empty(); endmodule"
        
        rtl_file = temp_dir / "empty.sv"
        rtl_file.write_text(rtl)
        
        features = extract_features(str(rtl_file))
        assert features["lines"] == 1
        assert features["assign"] == 0
        assert features["always_ff"] == 0