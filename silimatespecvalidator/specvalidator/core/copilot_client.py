from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class CopilotResult:
    rtl_text: str
    top_module: str
    meta: Dict[str, Any]


class CopilotClient:
    """
    Contract for Silimate copilot integration, this is just a fake integration,real integration can be done once given access.
    Real implementation can be HTTP/CLI/SDK later.
    """
    def rewrite(self, rtl_text: str, goal: str, context: Optional[Dict[str, Any]] = None) -> CopilotResult:
        raise NotImplementedError
