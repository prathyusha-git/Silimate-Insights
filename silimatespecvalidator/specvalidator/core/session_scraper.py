from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional
import json


@dataclass
class SuggestionAttempt:
    suggestion_id: str
    generated: Dict[str, Any] = field(default_factory=dict)   # suggestion_generated
    evaluation: Dict[str, Any] = field(default_factory=dict)  # evaluation_result
    action: Dict[str, Any] = field(default_factory=dict)      # action_taken

    def rtl_before_ref(self) -> Optional[str]:
        return self.generated.get("rtl_before_ref")

    def rtl_after_ref(self) -> Optional[str]:
        return self.generated.get("rtl_after_ref")


@dataclass
class SessionRecord:
    session_id: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    design_context: Dict[str, Any] = field(default_factory=dict)
    baseline_ppa: Dict[str, Any] = field(default_factory=dict)
    suggestions: Dict[str, SuggestionAttempt] = field(default_factory=dict)

    def get_or_create_attempt(self, suggestion_id: str) -> SuggestionAttempt:
        if suggestion_id not in self.suggestions:
            self.suggestions[suggestion_id] = SuggestionAttempt(suggestion_id=suggestion_id)
        return self.suggestions[suggestion_id]

#all we wanna do with this is, you give it a log file and a session id and it returns a neat "summary object" of that session, where each suggestion and its lifecycle are organised instead of being scattered across raw json lines
class SessionScraper:
    """
    Scrapes a 'deep' session from an event stream.
    Today: JSONL file.
    Later: swap the source to Silimate API/DB and yield the same events.
    """

    def scrape_from_jsonl(self, jsonl_path: str | Path, session_id: str) -> SessionRecord:
        jsonl_path = Path(jsonl_path)
        session = SessionRecord(session_id=session_id)

        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)

                if ev.get("session_id") != session_id:
                    continue

                session.events.append(ev)

                et = ev.get("event_type")
                if et == "design_context":
                    session.design_context = ev
                elif et == "baseline_ppa":
                    session.baseline_ppa = ev

                # suggestion-related
                sugg_id = ev.get("suggestion_id")
                if sugg_id:
                    attempt = session.get_or_create_attempt(sugg_id)

                    if et == "suggestion_generated":
                        attempt.generated = ev
                    elif et == "evaluation_result":
                        attempt.evaluation = ev
                    elif et == "action_taken":
                        attempt.action = ev

        return session

    # Later you add:
    # def scrape_from_api(self, base_url: str, token: str, session_id: str) -> SessionRecord:
    # def scrape_from_db(self, conn_str: str, session_id: str) -> SessionRecord:
