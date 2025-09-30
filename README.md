# Silimate Insights

Silimate Insights is a data analytics project that looks at how an AI copilot for chip design might actually be used in practice.  
The idea is to simulate product telemetry (usage logs, performance data, and model quality signals) and then turn it into dashboards and reports that show:

- How people are using the copilot (which features get the most use, adoption across customers).  
- Where it helps and where it doesn’t (customer satisfaction vs. friction points).  
- How well the AI model behaves (latency, errors, confidence, hallucinations).  
- What all this means for improving the product and guiding future training.  

This project is not about chip design itself — it’s about the **analytics layer** that helps founders, engineers, and product teams make better decisions.

---

## Goals

- Build synthetic telemetry data to mimic real copilot usage.  
- Process the data with Python into clean, meaningful metrics.  
- Create dashboards for adoption, quality, trust gaps, and design intent deviation.  
- Write an insights report that ties data back to product, engineering, and customer outcomes.  

---

## Repo Structure

silimate-insights/
│

├── data/ # raw and processed datasets

├── notebooks/ # Jupyter notebooks for exploration

├── src/ # Python scripts for data generation and ETL

├── dashboards/ # Streamlit/Grafana configs

├── reports/ # analysis reports
│
├── project_goals.md # full project plan

├── coding_standards.md # checklist for clean Python code

├── README.md # this file

└── requirements.txt # Python dependencies

---

## How to Run

1. Clone the repo:  
   ```bash
   git clone https://github.com/<your-username>/silimate-insights.git
   cd silimate-insights

2. Install Dependencies:
pip install -r requirements.txt

3. Generate the Sample Data:
python src/generate_data.py

4. Run ETL pipeline (produces processed CSV/SQLite in data/processed/):
python src/etl_pipeline.py

5. Setup Grafana
Download and install Grafana
Start Grafana locally (grafana-server).
In the Grafana UI, add data/processed/ as a data source (e.g., CSV, SQLite).
Import the dashboards from the dashboards/ folder (JSON files).

## Deliverables:

Synthetic dataset of simulated telemetry.

ETL pipeline for cleaning and processing.

Grafana dashboards (JSON configs in dashboards/):

Design Intent Deviation

Trust Gap (rejections, fallbacks, low-confidence)

Adoption Heatmap

Error & Latency Trends

Insights report with key findings.
