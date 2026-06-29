# silimatespecvalidator/specvalidator/eda_integration/questa.py

import subprocess
#run other programs like computer(like command-line tools)
from pathlib import Path
#brings in a helper named path, that makes it easier to work with file system paths, folders and filenames
import tempfile
#brings in a helper that can create tempoarary folder and files that are automatically cleaned up when you are done
class MentorQuesta:
    """Wrapper for Mentor/Siemens Questa simulator"""
 #A class is like a blueprint for creating objects that bundle data and functions together.   
    def __init__(self):
        self.tool_name = "questa"
     #this is a class's constructor.It runs automatically whenever you create a new mentorquesta() object    
    def is_available(self):
        """Check if Questa is available"""
        try:
            result = subprocess.run(["vsim", "-version"], capture_output=True, text=True)
            return "Questa" in result.stdout or "ModelSim" in result.stdout
        except FileNotFoundError:
            return False
    
    def compile_verilog(self, rtl_files, work_lib="work"):
        """Compile Verilog/SystemVerilog files"""
        with tempfile.TemporaryDirectory() as work_dir:
            work_path = Path(work_dir)
            
            # Create work library
            subprocess.run(["vlib", work_lib], cwd=work_path)
            
            # Compile files
            cmd = ["vlog", "-sv", "-work", work_lib] + list(rtl_files)
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_path)
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "work_dir": work_path if result.returncode == 0 else None
            }
    
    def run_simulation(self, top_module, work_dir, runtime="1us"):
        """Run Questa simulation"""
        cmd = [
            "vsim",
            "-c",  # Command line mode
            "-do", f"run {runtime}; quit",
            f"work.{top_module}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr
        }