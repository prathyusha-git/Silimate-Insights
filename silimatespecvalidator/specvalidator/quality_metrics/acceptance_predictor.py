# silimatespecvalidator/specvalidator/quality_metrics/acceptance_predictor.py

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import json
import numpy as np
from pathlib import Path

@dataclass
class PredictionResult:
    accept_probability: float
    reject_reason: str
    confidence: float

class AcceptancePredictor:
    """ML model for predicting suggestion acceptance"""
    
    def __init__(self, model_path: Path = None):
        self.model_path = model_path
        self.feature_weights = self._load_model()
    
    def _load_model(self) -> Dict[str, float]:
        """Load pre-trained model weights"""
        # Simplified linear model for demo
        return {
            'meets_ppa': 0.4,
            'confidence_score': 0.2,
            'rtl_line_delta': -0.1,
            'operator_delta': -0.05,
            'latency_penalty': -0.15,
            'user_history': 0.2
        }
    
    def extract_features(self, suggestion: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from suggestion data"""
        features = {}
        
        # PPA compliance
        features['meets_ppa'] = 1.0 if suggestion.get('fail_mode') == 'PASS' else 0.0
        
        # Confidence
        features['confidence_score'] = suggestion.get('confidence', 0.5)
        
        # RTL changes
        features['rtl_line_delta'] = abs(suggestion.get('delta_lines', 0)) / 100
        features['operator_delta'] = abs(suggestion.get('delta_operators', 0)) / 20
        
        # Latency
        latency = suggestion.get('latency_ms', 1000)
        features['latency_penalty'] = min(1.0, latency / 5000)
        
        # User history (simplified)
        features['user_history'] = suggestion.get('user_accept_rate', 0.5)
        
        return features
    
    def predict(self, suggestion: Dict[str, Any]) -> PredictionResult:
        """Predict acceptance probability"""
        features = self.extract_features(suggestion)
        
        # Simple linear model
        score = 0.5  # Base probability
        for feat, value in features.items():
            if feat in self.feature_weights:
                score += self.feature_weights[feat] * value
        
        # Sigmoid to get probability
        accept_prob = 1.0 / (1.0 + np.exp(-score))
        
        # Determine likely rejection reason
        reject_reason = "Unknown"
        if features['meets_ppa'] == 0:
            reject_reason = "PPA targets not met"
        elif features['confidence_score'] < 0.5:
            reject_reason = "Low confidence"
        elif features['latency_penalty'] > 0.5:
            reject_reason = "High latency"
        
        return PredictionResult(
            accept_probability=accept_prob,
            reject_reason=reject_reason,
            confidence=features['confidence_score']
        )