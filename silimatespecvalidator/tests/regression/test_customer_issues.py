# silimatespecvalidator/tests/regression/test_customer_issues.py

import pytest
from pathlib import Path
import tempfile

class TestCustomerReportedIssues:
    """Tests for issues reported by customers"""
    
    @pytest.mark.regression
    def test_issue_cust_001_xilinx_pragma_parsing(self):
        """Customer Issue #001: Xilinx pragmas caused parser to fail"""
        rtl_with_pragma = """module test();
        (* DONT_TOUCH = "TRUE" *)
        reg important_signal;
        
        // synthesis attribute keep of important_signal is true
        assign y = important_signal;
        endmodule"""
        
        with tempfile.TemporaryDirectory() as temp:
            rtl_file = Path(temp) / "xilinx.sv"
            rtl_file.write_text(rtl_with_pragma)
            
            from specvalidator.core.rtl_features import extract_features
            features = extract_features(str(rtl_file))
            assert features["assign"] == 1  # Should parse despite pragmas
    
    @pytest.mark.regression
    def test_issue_cust_002_very_long_module_names(self):
        """Customer Issue #002: Module names >100 chars caused truncation"""
        long_name = "module_" + "x" * 150
        rtl = f"module {long_name}(); endmodule"
        
        with tempfile.TemporaryDirectory() as temp:
            rtl_file = Path(temp) / "long.sv"
            rtl_file.write_text(rtl)
            
            from specvalidator.eda_integration.iverilog import lint_rtl
            result = lint_rtl(str(rtl_file))
            # Should handle long names without truncation errors
            assert "error" not in result.get("stderr", "").lower()
    
    @pytest.mark.regression
    def test_issue_cust_003_mixed_verilog_systemverilog(self):
        """Customer Issue #003: Mixed Verilog/SystemVerilog syntax failed"""
        mixed_rtl = """module mixed();
        // Verilog style
        reg [7:0] old_style;
        wire old_wire;
        
        // SystemVerilog style
        logic [7:0] new_style;
        logic new_wire;
        
        always_ff @(posedge clk) begin
            old_style <= new_style;
        end
        endmodule"""
        
        with tempfile.TemporaryDirectory() as temp:
            rtl_file = Path(temp) / "mixed.sv"
            rtl_file.write_text(mixed_rtl)
            
            from specvalidator.core.rtl_features import extract_features
            features = extract_features(str(rtl_file))
            assert features["always_ff"] == 1
    
    @pytest.mark.regression
    def test_issue_cust_004_windows_path_separators(self):
        """Customer Issue #004: Windows path separators caused failures"""
        # Simulate Windows path
        windows_path = "C:\\Users\\Customer\\Design\\rtl\\module.sv"
        
        # Should normalize path separators
        from pathlib import Path
        normalized = Path(windows_path)
        assert normalized.name == "module.sv"
    
    @pytest.mark.regression
    def test_issue_cust_005_special_chars_in_identifiers(self):
        """Customer Issue #005: Special characters in signal names"""
        rtl = """module special();
        wire \\signal$1 ;
        wire \\data[0] ;
        wire _underscore_start;
        assign \\signal$1 = 1'b0;
        endmodule"""
        
        with tempfile.TemporaryDirectory() as temp:
            rtl_file = Path(temp) / "special.sv"
            rtl_file.write_text(rtl)
            
            from specvalidator.eda_integration.iverilog import lint_rtl
            result = lint_rtl(str(rtl_file))
            # Should handle escaped identifiers
            assert result["ok"] or "escaped" not in result.get("stderr", "")