from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import json


@dataclass
class SessionEvents:
    session_id: str
    events: List[Dict[str, Any]]

    def by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e.get("event_type") == event_type]


def load_session_jsonl(jsonl_path: str | Path, session_id: str | None = None) -> SessionEvents:
    p = Path(jsonl_path)
    lines = p.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]

    if not events:
        raise ValueError(f"No events in {p}")

    if session_id is None:
        session_id = events[0].get("session_id")
        if not session_id:
            raise ValueError("session_id not found in first event")

    sess_events = [e for e in events if e.get("session_id") == session_id]
    if not sess_events:
        raise ValueError(f"No events found for session_id={session_id} in {p}")

    return SessionEvents(session_id=session_id, events=sess_events)
