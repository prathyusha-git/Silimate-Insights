# silimatespecvalidator/specvalidator/eda_integration/__init__.py
#any folder that has a file named _init_.py becomes a python package
#Tell Python what this folder represents
#control what gets exposed when someone imports this module
#Act as the entry point for the eda_integration package
#Connects multiple EDA tools (Icarus Verilog, VCS, Questa, etc.)
#Automatically detects which tools are installed
#Provides simple helper functions like:
#quick_lint()
#quick_simulate()
"""
EDA Tool Integration Module for SpecValidator

Provides unified interfaces for major EDA tools:
- Iverilog (open source)
- Synopsys VCS
- Cadence Xcelium
- Mentor/Siemens Questa
- Verilator
"""

# Import main components
from .iverilog import lint_rtl, run_simulation
#import two functions lint_rtl, run_simulation from iverilog.py file which is in the same folder as this
# Import tool classes (only if files exist)
try:
    from .vcs import SynopsysVCS
except ImportError:
    SynopsysVCS = None
#if the vcs integration file exists, import it, if not just set it to none and continue
try:
    from .xcelium import CadenceXcelium
except ImportError:
    CadenceXcelium = None
#if the 
try:
    from .questa import MentorQuesta
except ImportError:
    MentorQuesta = None

try:
    from .verilator import Verilator
except ImportError:
    Verilator = None

try:
    from .wrapper import EDAToolWrapper
except ImportError:
    EDAToolWrapper = None

# Version info
__version__ = "1.0.0"

# Default tool priority order
DEFAULT_TOOL_PRIORITY = [
    'iverilog',    # Always available, open source
    'verilator',   # Fast, open source
    'vcs',         # Industry standard
    'xcelium',     # Cadence
    'questa'       # Mentor/Siemens
]
#this list above defines preference order, not availability.
def get_available_tools():
    """
    Detect which EDA tools are available on this system
    
    Returns:
        list: Names of available EDA tools
    """
    import subprocess
    available = []
    
    #It literally runs quick terminal commands like iverilog -V or verilator --version.
    # Check each tool and gives first priority order wise
    tool_checks = {
        'iverilog': ['iverilog', '-V'],
        'verilator': ['verilator', '--version'],
        'vcs': ['vcs', '-ID'],
        'xcelium': ['xrun', '-version'],
        'questa': ['vsim', '-version']
    }
    
    for tool_name, check_cmd in tool_checks.items():
        try:
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                available.append(tool_name)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    return available
#provides easy mode helper fuctions
def auto_select_tool(prefer_open_source=True):
    """
    Automatically select the best available EDA tool
    
    Args:
        prefer_open_source: If True, prefer open source tools
    
    Returns:
        str: Name of selected tool, or None if no tools available
    """
    available = get_available_tools()
    
    if not available:
        return None
    
    if prefer_open_source:
        # Prefer open source tools
        for tool in ['iverilog', 'verilator']:
            if tool in available:
                return tool
    
    # Return first available from priority order
    for tool in DEFAULT_TOOL_PRIORITY:
        if tool in available:
            return tool
    
    return available[0]

# Convenience functions for quick access, if the tool is auto, automatically select tool
def quick_lint(rtl_file, tool='auto'):
    """
    Quick lint function using best available tool
    
    Args:
        rtl_file: Path to RTL file
        tool: Tool name or 'auto' for automatic selection
    
    Returns:
        dict: Lint results with 'ok' and 'messages' keys
    """
    if tool == 'auto':
        tool = auto_select_tool()
        if not tool:
            return {"ok": False, "messages": "No EDA tools available"}
    
    if tool == 'iverilog':
        return lint_rtl(rtl_file)
    
    # Add other tools as needed
    return {"ok": False, "messages": f"Tool {tool} not implemented"}

def quick_simulate(rtl_file, top_module, inputs, tool='auto'):
    """
    Quick simulation function
    """
    if tool == 'auto':
        tool = auto_select_tool()
        if not tool:
            return {"ok": False, "messages": "No EDA tools available"}

    if tool == 'iverilog':
        return run_simulation(rtl_file, top_module, inputs)

    # Add other tools as needed
    return {"ok": False, "messages": f"Tool {tool} not implemented"}
