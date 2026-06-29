# silimatespecvalidator/specvalidator/dashboard/reports.py

from pathlib import Path
import pandas as pd
from datetime import datetime
from typing import Dict, Any

class ReportGenerator:
    """Generate PDF/HTML reports"""
    
    def generate_html_report(self, data: pd.DataFrame, output_path: Path) -> Path:
        """Generate HTML report"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SpecValidator Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .metric {{ font-size: 24px; font-weight: bold; }}
                .good {{ color: green; }}
                .warning {{ color: orange; }}
                .bad {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>Silimate SpecValidator QA Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <h2>Summary Metrics</h2>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>Total Sessions</td>
                    <td class="metric">{len(data['session_id'].unique())}</td>
                    <td class="good">✓</td>
                </tr>
                <tr>
                    <td>Acceptance Rate</td>
                    <td class="metric">{(data['action']=='accept').mean():.1%}</td>
                    <td class="{'good' if (data['action']=='accept').mean() > 0.7 else 'warning'}">
                        {'✓' if (data['action']=='accept').mean() > 0.7 else '⚠'}
                    </td>
                </tr>
                <tr>
                    <td>PPA Pass Rate</td>
                    <td class="metric">{(data['fail_mode']=='PASS').mean():.1%}</td>
                    <td class="{'good' if (data['fail_mode']=='PASS').mean() > 0.6 else 'warning'}">
                        {'✓' if (data['fail_mode']=='PASS').mean() > 0.6 else '⚠'}
                    </td>
                </tr>
            </table>
            
            <h2>Recent Sessions</h2>
            {data.head(10).to_html(index=False)}
        </body>
        </html>
        """
        
        output_path.write_text(html)
        return output_path