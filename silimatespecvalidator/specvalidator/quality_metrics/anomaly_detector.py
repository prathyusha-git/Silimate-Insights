# silimatespecvalidator/specvalidator/quality_metrics/anomaly_detector.py

from typing import Dict, Any, List
import numpy as np
from collections import deque

class AnomalyDetector:
    """Detect quality regressions and anomalies"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics_history = {
            'acceptance_rate': deque(maxlen=window_size),
            'ppa_pass_rate': deque(maxlen=window_size),
            'avg_confidence': deque(maxlen=window_size),
            'avg_latency': deque(maxlen=window_size)
        }
        self.thresholds = {
            'acceptance_rate': 0.3,  # Alert if drops below 30%
            'ppa_pass_rate': 0.5,    # Alert if drops below 50%
            'avg_confidence': 0.6,   # Alert if drops below 60%
            'avg_latency': 3000      # Alert if exceeds 3000ms
        }
    
    def update(self, metrics: Dict[str, float]):
        """Update metrics history"""
        for key in self.metrics_history:
            if key in metrics:
                self.metrics_history[key].append(metrics[key])
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in recent metrics"""
        anomalies = []
        
        for metric, history in self.metrics_history.items():
            if len(history) < 10:
                continue  # Need minimum history
            
            recent = list(history)[-10:]
            mean = np.mean(recent)
            std = np.std(recent)
            
            # Check threshold violations
            if metric == 'avg_latency':
                if mean > self.thresholds[metric]:
                    anomalies.append({
                        'type': 'threshold_violation',
                        'metric': metric,
                        'value': mean,
                        'threshold': self.thresholds[metric],
                        'severity': 'high' if mean > self.thresholds[metric] * 1.5 else 'medium'
                    })
            else:
                if mean < self.thresholds[metric]:
                    anomalies.append({
                        'type': 'threshold_violation',
                        'metric': metric,
                        'value': mean,
                        'threshold': self.thresholds[metric],
                        'severity': 'high' if mean < self.thresholds[metric] * 0.5 else 'medium'
                    })
            
            # Check for sudden changes (>2 std dev)
            if len(history) >= 20:
                baseline = list(history)[-20:-10]
                baseline_mean = np.mean(baseline)
                if abs(mean - baseline_mean) > 2 * std:
                    anomalies.append({
                        'type': 'sudden_change',
                        'metric': metric,
                        'baseline': baseline_mean,
                        'current': mean,
                        'change': mean - baseline_mean,
                        'severity': 'medium'
                    })
        
        return anomalies