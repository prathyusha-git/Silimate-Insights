# silimatespecvalidator/tests/integration/test_dashboard.py

import pytest
import json
from pathlib import Path
import pandas as pd

class TestDashboardFunctionality:
    """Test dashboard data generation and metrics"""
    
    def test_dashboard_metrics_generation(self, tmp_path):
        """Test generating dashboard metrics from analysis results"""
        # Create sample results
        results = [
            {
                "session_id": "sess_001",
                "confidence": 0.85,
                "action": "accept",
                "fail_mode": "PASS",
                "action_alignment": "OK",
                "delta_power": -10,
                "delta_freq": 100,
                "delta_area": -1
            },
            {
                "session_id": "sess_002",
                "confidence": 0.75,
                "action": "reject",
                "fail_mode": "FAIL_AREA",
                "action_alignment": "OK",
                "delta_power": -5,
                "delta_freq": 50,
                "delta_area": 2
            }
        ]
        
        # Save as JSON (simulating analyzer output)
        results_file = tmp_path / "session_qa_results.json"
        results_file.write_text(json.dumps(results))
        
        # Calculate dashboard metrics
        data = json.loads(results_file.read_text())
        df = pd.DataFrame(data)
        
        metrics = {
            "total_suggestions": len(df),
            "acceptance_rate": (df["action"] == "accept").mean() * 100,
            "average_confidence": df["confidence"].mean(),
            "pass_rate": (df["fail_mode"] == "PASS").mean() * 100,
            "suspicious_rate": (df["action_alignment"].str.contains("SUSPICIOUS")).mean() * 100
        }
        
        assert metrics["total_suggestions"] == 2
        assert metrics["acceptance_rate"] == 50.0
        assert metrics["average_confidence"] == 0.80
        assert metrics["pass_rate"] == 50.0
        assert metrics["suspicious_rate"] == 0.0
    
    def test_trend_analysis(self, tmp_path):
        """Test trend analysis over time"""
        # Create time-series data
        sessions = []
        for day in range(5):
            for i in range(3):
                sessions.append({
                    "session_id": f"day{day}_sess{i}",
                    "timestamp": f"2024-01-0{day+1}",
                    "confidence": 0.7 + (day * 0.02),  # Improving over time
                    "fail_mode": "PASS" if day > 2 else "FAIL_POWER",
                    "action": "accept" if day > 2 else "reject"
                })
        
        df = pd.DataFrame(sessions)
        
        # Calculate daily metrics
        daily_metrics = df.groupby("timestamp").agg({
            "confidence": "mean",
            "action": lambda x: (x == "accept").mean() * 100
        })
        
        # Verify trend
        confidences = daily_metrics["confidence"].tolist()
        assert all(confidences[i] <= confidences[i+1] for i in range(len(confidences)-1))
    
    def test_failure_mode_distribution(self, tmp_path):
        """Test failure mode distribution calculation"""
        results = [
            {"fail_mode": "PASS"},
            {"fail_mode": "PASS"},
            {"fail_mode": "FAIL_POWER"},
            {"fail_mode": "FAIL_FREQ"},
            {"fail_mode": "FAIL_AREA"},
            {"fail_mode": "FAIL_POWER_AREA"},
        ]
        
        df = pd.DataFrame(results)
        distribution = df["fail_mode"].value_counts(normalize=True) * 100
        
        assert distribution["PASS"] == pytest.approx(33.33, 0.1)
        assert "FAIL_POWER" in distribution
        assert "FAIL_FREQ" in distribution
        assert "FAIL_AREA" in distribution
    
    def test_performance_improvement_metrics(self):
        """Test PPA improvement calculations"""
        results = [
            {"delta_power": -15, "delta_freq": 200, "delta_area": -2},
            {"delta_power": -10, "delta_freq": 150, "delta_area": -1},
            {"delta_power": 5, "delta_freq": -50, "delta_area": 1},
        ]
        
        df = pd.DataFrame(results)
        
        improvements = {
            "avg_power_reduction": -df["delta_power"].mean(),
            "avg_freq_improvement": df["delta_freq"].mean(),
            "avg_area_reduction": -df["delta_area"].mean()
        }
        
        assert improvements["avg_power_reduction"] == pytest.approx(6.67, 0.1)
        assert improvements["avg_freq_improvement"] == pytest.approx(100, 0.1)
        assert improvements["avg_area_reduction"] == pytest.approx(0.67, 0.1)
    
    def test_alert_generation(self):
        """Test generating alerts for anomalies"""
        results = [
            {"action_alignment": "OK", "confidence": 0.9},
            {"action_alignment": "SUSPICIOUS_REJECT", "confidence": 0.95},
            {"action_alignment": "RISKY_ACCEPT", "confidence": 0.4},
            {"action_alignment": "OK", "confidence": 0.85},
        ]
        
        df = pd.DataFrame(results)
        
        alerts = []
        
        # Check for suspicious patterns
        suspicious = df[df["action_alignment"].str.contains("SUSPICIOUS|RISKY")]
        if not suspicious.empty:
            alerts.append({
                "type": "suspicious_behavior",
                "count": len(suspicious),
                "details": suspicious["action_alignment"].tolist()
            })
        
        # Check for low confidence
        low_conf = df[df["confidence"] < 0.5]
        if not low_conf.empty:
            alerts.append({
                "type": "low_confidence",
                "count": len(low_conf),
                "avg_confidence": low_conf["confidence"].mean()
            })
        
        assert len(alerts) == 2
        assert alerts[0]["type"] == "suspicious_behavior"
        assert alerts[0]["count"] == 2
        assert alerts[1]["type"] == "low_confidence"
        assert alerts[1]["count"] == 1