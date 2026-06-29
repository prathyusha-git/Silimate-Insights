# silimatespecvalidator/specvalidator/dashboard/visualizations.py

import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from typing import Dict, Any

class Visualizer:
    """Generate charts and visualizations"""
    
    def __init__(self, output_dir: Path = Path("reports/charts")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def plot_ppa_distribution(self, data: pd.DataFrame) -> Path:
        """Plot PPA pass/fail distribution"""
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        # Power distribution
        axes[0].hist(data['delta_power'].dropna(), bins=20, color='blue', alpha=0.7)
        axes[0].set_title('Power Delta Distribution')
        axes[0].set_xlabel('Delta Power (mW)')
        
        # Frequency distribution
        axes[1].hist(data['delta_freq'].dropna(), bins=20, color='green', alpha=0.7)
        axes[1].set_title('Frequency Delta Distribution')
        axes[1].set_xlabel('Delta Frequency (MHz)')
        
        # Area distribution
        axes[2].hist(data['delta_area'].dropna(), bins=20, color='red', alpha=0.7)
        axes[2].set_title('Area Delta Distribution')
        axes[2].set_xlabel('Delta Area (um²)')
        
        output_path = self.output_dir / 'ppa_distribution.png'
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()
        
        return output_path
    
    def plot_acceptance_trend(self, data: pd.DataFrame) -> Path:
        """Plot acceptance rate over time"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Group by session and calculate acceptance rate
        grouped = data.groupby('session_id').agg({
            'action': lambda x: (x == 'accept').mean()
        })
        
        ax.plot(range(len(grouped)), grouped['action'], marker='o')
        ax.set_title('Acceptance Rate Trend')
        ax.set_xlabel('Session Index')
        ax.set_ylabel('Acceptance Rate')
        ax.grid(True, alpha=0.3)
        
        output_path = self.output_dir / 'acceptance_trend.png'
        plt.savefig(output_path)
        plt.close()
        
        return output_path