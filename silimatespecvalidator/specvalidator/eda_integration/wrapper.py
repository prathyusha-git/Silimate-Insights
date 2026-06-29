# silimatespecvalidator/specvalidator/eda_integration/wrapper.py

from .iverilog import lint_rtl, run_simulation
from .vcs import SynopsysVCS  
from .xcelium import CadenceXcelium
from .questa import MentorQuesta
from .verilator import Verilator

class EDAToolWrapper:
    """Unified interface for all EDA tools"""
    
    def __init__(self):
        self.tools = {
            'iverilog': {
                'lint': lint_rtl,
                'simulate': run_simulation,
                'available': self._check_iverilog
            },
            'vcs': SynopsysVCS(),
            'xcelium': CadenceXcelium(), 
            'questa': MentorQuesta(),
            'verilator': Verilator()
        }
        
        # Detect available tools
        self.available_tools = self._detect_tools()
    
    def _detect_tools(self):
        """Detect which EDA tools are available"""
        available = []
        
        # Check each tool
        if self._check_iverilog():
            available.append('iverilog')
        
        for name in ['vcs', 'xcelium', 'questa', 'verilator']:
            tool = self.tools[name]
            if hasattr(tool, 'is_available') and tool.is_available():
                available.append(name)
        
        return available
    
    def _check_iverilog(self):
        """Check if iverilog is available"""
        import subprocess
        try:
            result = subprocess.run(["iverilog", "-V"], capture_output=True)
            return result.returncode == 0
        except:
            return False
    
    def lint(self, rtl_file, tool=None):
        """Lint RTL with specified or available tool"""
        if tool is None:
            # Use first available tool
            if not self.available_tools:
                raise RuntimeError("No EDA tools available")
            tool = self.available_tools[0]
        
        if tool == 'iverilog':
            return self.tools['iverilog']['lint'](rtl_file)
        elif tool == 'vcs':
            result = self.tools['vcs'].compile([rtl_file], "top")
            return {"ok": result["success"], "stderr": result["errors"]}
        elif tool == 'xcelium':
            return self.tools['xcelium'].run_lint(rtl_file)
        elif tool == 'questa':
            result = self.tools['questa'].compile_verilog([rtl_file])
            return {"ok": result["success"], "stderr": result["errors"]}
        elif tool == 'verilator':
            return self.tools['verilator'].lint(rtl_file)
        else:
            raise ValueError(f"Unknown tool: {tool}")
    
    def get_tool_info(self):
        """Get information about available tools"""
        return {
            "available": self.available_tools,
            "total": len(self.tools),
            "details": {
                tool: {
                    "available": tool in self.available_tools,
                    "type": type(self.tools[tool]).__name__
                }
                for tool in self.tools
            }
        }