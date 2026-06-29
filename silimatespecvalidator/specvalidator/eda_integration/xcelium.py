# silimatespecvalidator/specvalidator/eda_integration/xcelium.py

import subprocess
import tempfile
from pathlib import Path

class CadenceXcelium:
    """Wrapper for Cadence Xcelium simulator"""
    
    def __init__(self):
        self.tool_name = "xcelium"
        
    def is_available(self):
        """Check if Xcelium is available"""
        try:
            result = subprocess.run(["xrun", "-version"], capture_output=True, text=True)
            return "Xcelium" in result.stdout
        except FileNotFoundError:
            return False
    
    def run_lint(self, rtl_file):
        """Run Xcelium linting"""
        cmd = [
            "xrun",
            "-compile",     # Compile only
            "-sv",          # SystemVerilog
            "-lint",        # Enable linting
            "-nowarn", "DLCPTH",  # Suppress path warnings
            "-nowarn", "DLCVAR",
            rtl_file
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse lint results
            warnings = []
            errors = []
            for line in result.stderr.split('\n'):
                if 'Warning' in line:
                    warnings.append(line)
                elif 'Error' in line:
                    errors.append(line)
            
            return {
                "ok": result.returncode == 0 and len(errors) == 0,
                "warnings": warnings,
                "errors": errors,
                "output": result.stdout
            }
        except Exception as e:
            return {
                "ok": False,
                "warnings": [],
                "errors": [str(e)],
                "output": ""
            }
    
    def compile_and_elaborate(self, rtl_files, top_module):
        """Compile and elaborate design"""
        with tempfile.TemporaryDirectory() as work_dir:
            cmd = [
                "xrun",
                "-elaborate",
                "-sv",
                "-top", top_module,
                "-work", work_dir,
            ] + list(rtl_files)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr
            }