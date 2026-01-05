from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any
from .copilot_client import CopilotClient, CopilotResult


class FakeCopilotClient(CopilotClient):
    """
    Fake copilot: returns a known rewrite RTL from examples/.
    This lets SpecValidator run end-to-end without Silimate access.
    """

    def __init__(self, rewrite_path: str = "examples/rewrite_logic.sv", top_module: str = "rewrite_logic"):
        self.rewrite_path = Path(rewrite_path)
        self.top_module = top_module

    def rewrite(self, rtl_text: str, goal: str, context: Optional[Dict[str, Any]] = None) -> CopilotResult:
        rtl = self.rewrite_path.read_text(encoding="utf-8")
        return CopilotResult(
            rtl_text=rtl,
            top_module=self.top_module,
            meta={
                "mode": "fake",
                "goal": goal,
                "context": context or {},
            },
        )
