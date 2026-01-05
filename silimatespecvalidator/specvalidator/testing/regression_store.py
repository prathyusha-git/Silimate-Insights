from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, Any, Iterable, List

DEFAULT_PATH = Path("regressions") / "equiv_vectors.jsonl"

def append_failure(inputs: Dict[str, int], meta: Dict[str, Any] | None = None, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "inputs": inputs,
        "meta": meta or {},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def load_failures(path: Path = DEFAULT_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out
