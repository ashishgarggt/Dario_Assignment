import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json
from etl import main as run_etl  # reuse ETL function

PROCESSED_DIR = Path("data/processed")
st.set_page_config(page_title="COVID-19 Dashboard", layout="wide")

st.title("🦠 Global COVID-19 Trends")
st.markdown("Interactive dashboard with real data from **disease.sh** (no API key)")

# ------------------- Sidebar Widgets -------------------
st.sidebar.header("🌍 Data Controls")

# Country selection – you can expand this list or let user type
COUNTRIES = ["USA", "India", "Germany", "France", "Brazil", "Japan", "UK", "Italy", "Spain", "Mexico"]
selected_country = st.sidebar.selectbox("Select Country", COUNTRIES)

# Days of history
days_back = st.sidebar.slider("Historical days", 30, 180, 90, step=30)

# Fetch fresh data when country or days changes
@st.cache_data(ttl=3600)  # cache for 1 hour
def get_data(country, days):
    df = run_etl(country, days)
    if df is None:
        return None, None
    with open(PROCESSED_DIR / f"{country}_quality.json", "r") as f:
        quality = json.load(f)
    return df, quality

df, quality = get_data(selected_country, days_back)

if df is None:
    st.error(f"Could not fetch data for {selected_country}. Try another country.")
    st.stop()

# ------------------- Metric Selection -------------------
st.sidebar.header("📈 Chart Settings")
metric_options = {
    "Daily New Cases": "new_cases",
    "Daily New Deaths": "new_deaths",
    "Total Cases": "total_cases",
    "Total Deaths": "total_deaths",
    "7-day MA (Cases)": "new_cases_ma7",
    "7-day MA (Deaths)": "new_deaths_ma7"
}
selected_metric = st.sidebar.selectbox("Metric to display", list(metric_options.keys()))
metric_col = metric_options[selected_metric]

chart_type = st.sidebar.radio("Chart type", ["Line", "Bar", "Area"])
log_scale = st.sidebar.checkbox("Logarithmic scale (Y-axis)", value=False)
show_ma = st.sidebar.checkbox("Show 7-day moving average", value=True) if "New" in selected_metric else False

# Date range filter
min_date = df["date"].min().date()
max_date = df["date"].max().date()
date_range = st.sidebar.date_input("Date range", [min_date, max_date], min_value=min_date, max_value=max_date)
mask = (df["date"] >= pd.Timestamp(date_range[0])) & (df["date"] <= pd.Timestamp(date_range[1]))
filtered = df[mask]

# ------------------- Main KPIs -------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Cases", f"{filtered['total_cases'].iloc[-1]:,.0f}")
col2.metric("Total Deaths", f"{filtered['total_deaths'].iloc[-1]:,.0f}")
col3.metric("Latest New Cases", f"{filtered['new_cases'].iloc[-1]:,.0f}")
col4.metric("Quality Score", f"{quality['quality_score']}/100")

# ------------------- Plot -------------------
fig = None
if chart_type == "Line":
    fig = px.line(filtered, x="date", y=metric_col, title=f"{selected_metric} in {selected_country}")
elif chart_type == "Bar":
    fig = px.bar(filtered, x="date", y=metric_col, title=f"{selected_metric} in {selected_country}")
else:
    fig = px.area(filtered, x="date", y=metric_col, title=f"{selected_metric} in {selected_country}")

fig.update_layout(yaxis_type="log" if log_scale else "linear")
st.plotly_chart(fig, use_container_width=True)

# Optional: Add moving average line if not already part of the metric
if show_ma and "New" in selected_metric:
    ma_col = "new_cases_ma7" if "Cases" in selected_metric else "new_deaths_ma7"
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=filtered["date"], y=filtered[metric_col], name=selected_metric, mode='lines'))
    fig2.add_trace(go.Scatter(x=filtered["date"], y=filtered[ma_col], name="7-day MA", mode='lines', line=dict(dash='dot')))
    fig2.update_layout(title=f"{selected_metric} with 7-day MA", yaxis_type="log" if log_scale else "linear")
    st.plotly_chart(fig2, use_container_width=True)

# ------------------- Data Table (collapsible) -------------------
with st.expander("📋 View Raw Data (filtered)"):
    st.dataframe(filtered.tail(30))

# ------------------- Quality Report -------------------
with st.expander("🔍 Data Quality Details"):
    st.json(quality)

# ------------------- Extra: Compare two countries -------------------
st.sidebar.header("🔁 Compare Countries")
compare = st.sidebar.checkbox("Compare with another country")
if compare:
    country2 = st.sidebar.selectbox("Second country", [c for c in COUNTRIES if c != selected_country])
    metric2 = st.sidebar.selectbox("Metric for comparison", list(metric_options.keys()), index=0)
    df2, _ = get_data(country2, days_back)
    if df2 is not None:
        # Filter same date range
        df2_filtered = df2[(df2["date"] >= pd.Timestamp(date_range[0])) & (df2["date"] <= pd.Timestamp(date_range[1]))]
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Scatter(x=filtered["date"], y=filtered[metric_options[metric2]], name=f"{selected_country} - {metric2}"))
        fig_comp.add_trace(go.Scatter(x=df2_filtered["date"], y=df2_filtered[metric_options[metric2]], name=f"{country2} - {metric2}"))
        fig_comp.update_layout(title=f"Comparison: {selected_country} vs {country2}", yaxis_type="log" if log_scale else "linear")
        st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.warning(f"Could not load data for {country2}")
