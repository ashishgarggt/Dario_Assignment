import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import json

PROCESSED_DIR = Path("data/processed")

st.set_page_config(page_title="Healthcare Dashboard", layout="wide")
st.title("🏥 COVID‑19 Healthcare Trends")

@st.cache_data
def load_data():
    df = pd.read_csv(PROCESSED_DIR / "covid_data.csv", parse_dates=["date"])
    with open(PROCESSED_DIR / "quality_report.json") as f:
        qual = json.load(f)
    return df, qual

try:
    df, quality = load_data()
except:
    st.error("Run `python etl.py` first to generate data.")
    st.stop()

# Sidebar filters
st.sidebar.header("Filters")
date_range = st.sidebar.date_input(
    "Date range",
    [df["date"].min(), df["date"].max()],
    min_value=df["date"].min(),
    max_value=df["date"].max()
)
mask = (df["date"] >= pd.Timestamp(date_range[0])) & (df["date"] <= pd.Timestamp(date_range[1]))
filtered = df[mask]

# KPIs
col1, col2, col3 = st.columns(3)
col1.metric("Total Cases", f"{filtered['total_cases'].iloc[-1]:,.0f}")
col2.metric("Total Deaths", f"{filtered['total_deaths'].iloc[-1]:,.0f}")
col3.metric("Latest New Cases", f"{filtered['new_cases'].iloc[-1]:,.0f}")

# Chart
fig = px.line(filtered, x="date", y=["new_cases", "new_cases_ma7"],
              title="Daily New Cases (with 7‑day moving average)",
              labels={"value": "Cases", "date": "Date", "variable": "Metric"})
st.plotly_chart(fig, use_container_width=True)

# Quality report
with st.expander("📊 Data Quality Report"):
    st.metric("Quality Score", f"{quality['quality_score']}/100")
    st.write(f"Missing date gaps: {quality['missing_date_gaps']}")
    st.write(f"Negative new cases: {quality['negative_new_cases']}")
    st.write(f"Outlier days: {quality['outlier_days']}")
