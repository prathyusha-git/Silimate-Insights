# silimatespecvalidator/specvalidator/testing/golden_store.py

from __future__ import annotations
from pathlib import Path
import json
from typing import Dict, Any, List, Optional
import hashlib

class GoldenStore:
    """Store and manage golden reference outputs for regression testing"""
    
    def __init__(self, store_path: Path = Path("golden_refs")):
        self.store_path = store_path
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_path / "index.json"
        self.index = self._load_index()
    
    def _load_index(self) -> Dict[str, Any]:
        """Load the golden reference index"""
        if self.index_file.exists():
            return json.loads(self.index_file.read_text())
        return {}
    
    def _save_index(self):
        """Save the golden reference index"""
        self.index_file.write_text(json.dumps(self.index, indent=2))
    
    def store_golden(self, test_id: str, rtl_file: str, outputs: Dict[str, Any]) -> str:
        """Store a golden reference output"""
        # Generate unique hash for this golden reference
        content = f"{test_id}:{rtl_file}:{json.dumps(outputs, sort_keys=True)}"
        ref_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Store the golden output
        golden_file = self.store_path / f"golden_{ref_hash}.json"
        golden_data = {
            "test_id": test_id,
            "rtl_file": rtl_file,
            "outputs": outputs,
            "hash": ref_hash
        }
        golden_file.write_text(json.dumps(golden_data, indent=2))
        
        # Update index
        self.index[test_id] = {
            "hash": ref_hash,
            "rtl_file": rtl_file,
            "file": str(golden_file)
        }
        self._save_index()
        
        return ref_hash
    
    def get_golden(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a golden reference output"""
        if test_id not in self.index:
            return None
        
        golden_file = Path(self.index[test_id]["file"])
        if not golden_file.exists():
            return None
        
        return json.loads(golden_file.read_text())
    
    def compare_with_golden(self, test_id: str, actual_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Compare actual outputs with golden reference"""
        golden = self.get_golden(test_id)
        if not golden:
            return {"match": False, "error": "No golden reference found"}
        
        expected = golden["outputs"]
        
        # Deep comparison
        mismatches = []
        for key in expected:
            if key not in actual_outputs:
                mismatches.append(f"Missing key: {key}")
            elif expected[key] != actual_outputs[key]:
                mismatches.append(f"Mismatch in {key}: expected {expected[key]}, got {actual_outputs[key]}")
        
        for key in actual_outputs:
            if key not in expected:
                mismatches.append(f"Unexpected key: {key}")
        
        return {
            "match": len(mismatches) == 0,
            "mismatches": mismatches,
            "golden_hash": golden["hash"]
        }