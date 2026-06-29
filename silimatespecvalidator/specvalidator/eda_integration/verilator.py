# silimatespecvalidator/specvalidator/eda_integration/verilator.py

import subprocess
import tempfile
from pathlib import Path

class Verilator:
    """Wrapper for Verilator (open source)"""
    
    def __init__(self):
        self.tool_name = "verilator"
        
    def is_available(self):
        """Check if Verilator is available"""
        try:
            result = subprocess.run(["verilator", "--version"], capture_output=True, text=True)
            return "Verilator" in result.stdout
        except FileNotFoundError:
            return False
    
    def lint(self, rtl_file):
        """Lint SystemVerilog with Verilator"""
        cmd = [
            "verilator",
            "--lint-only",
            "-Wall",
            "--sv",
            rtl_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return {
            "ok": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr
        }
    
    def compile_to_cpp(self, rtl_files, top_module):
        """Compile Verilog to C++ for fast simulation"""
        with tempfile.TemporaryDirectory() as obj_dir:
            cmd = [
                "verilator",
                "--cc",  # C++ output
                "--exe", # Build executable
                "--build",  # Build immediately
                "--top-module", top_module,
                "-o", "Vsim",
                "--Mdir", obj_dir
            ] + list(rtl_files)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "executable": Path(obj_dir) / "Vsim" if result.returncode == 0 else None
            }