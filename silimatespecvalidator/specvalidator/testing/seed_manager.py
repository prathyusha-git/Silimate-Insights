# silimatespecvalidator/specvalidator/testing/seed_manager.py

from __future__ import annotations
import random
from pathlib import Path
import json
from typing import List, Optional, Dict, Any

class SeedManager:
    """Manage random seeds for reproducible testing"""
    
    def __init__(self, base_seed: int = 42):
        self.base_seed = base_seed
        self.current_seed = base_seed
        self.seed_history = []
        self.rng = random.Random(base_seed)
    
    def set_seed(self, seed: int):
        """Set a specific seed"""
        self.current_seed = seed
        self.rng = random.Random(seed)
        random.seed(seed)  # Also set global random seed
        self.seed_history.append(seed)
    
    def get_next_seed(self) -> int:
        """Get next deterministic seed"""
        next_seed = self.rng.randint(0, 2**32 - 1)
        self.set_seed(next_seed)
        return next_seed
    
    def save_seeds(self, path: Path):
        """Save seed history for reproduction"""
        data = {
            "base_seed": self.base_seed,
            "current_seed": self.current_seed,
            "history": self.seed_history
        }
        path.write_text(json.dumps(data, indent=2))
    
    def load_seeds(self, path: Path):
        """Load seed history"""
        data = json.loads(path.read_text())
        self.base_seed = data["base_seed"]
        self.current_seed = data["current_seed"]
        self.seed_history = data["history"]
        self.set_seed(self.current_seed)
    
    def generate_test_vectors(self, n_bits: int = 8, n_vectors: int = 10) -> List[Dict[str, int]]:
        """Generate reproducible test vectors"""
        vectors = []
        for _ in range(n_vectors):
            vector = {}
            for signal in ['a', 'b', 'c']:
                vector[signal] = self.rng.randint(0, 2**n_bits - 1)
            vectors.append(vector)
        return vectors