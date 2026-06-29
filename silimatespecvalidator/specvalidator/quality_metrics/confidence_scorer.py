# silimatespecvalidator/specvalidator/quality_metrics/confidence_scorer.py

from typing import Dict, Any, List
import numpy as np

class ConfidenceScorer:
    """Calculate confidence scores for suggestions"""
    
    def __init__(self):
        self.weights = {
            'ppa_pass_rate': 0.3,
            'rtl_complexity': 0.2,
            'historical_acceptance': 0.25,
            'latency_factor': 0.15,
            'user_alignment': 0.1
        }
    
    def calculate_confidence(self, metrics: Dict[str, Any]) -> float:
        """Calculate weighted confidence score"""
        score = 0.0
        
        # PPA success rate (0-1)
        if 'ppa_pass_rate' in metrics:
            score += self.weights['ppa_pass_rate'] * metrics['ppa_pass_rate']
        
        # RTL complexity factor (inverse - simpler is better)
        if 'rtl_complexity' in metrics:
            complexity_score = 1.0 / (1.0 + metrics['rtl_complexity'])
            score += self.weights['rtl_complexity'] * complexity_score
        
        # Historical acceptance rate
        if 'historical_acceptance' in metrics:
            score += self.weights['historical_acceptance'] * metrics['historical_acceptance']
        
        # Latency factor (faster is better)
        if 'latency_ms' in metrics:
            latency_score = max(0, 1.0 - (metrics['latency_ms'] / 5000))
            score += self.weights['latency_factor'] * latency_score
        
        # User alignment
        if 'user_alignment' in metrics:
            score += self.weights['user_alignment'] * metrics['user_alignment']
        
        return min(1.0, max(0.0, score))
    
    def batch_score(self, suggestions: List[Dict[str, Any]]) -> List[float]:
        """Score multiple suggestions"""
        return [self.calculate_confidence(s) for s in suggestions]