
---

### 3. `etl.py`

```python
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import os

# Create folders
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ------------------- Extraction -------------------
def fetch_covid_data(country="USA", days=60):
    """Free healthcare API, no key needed"""
    url = f"https://disease.sh/v3/covid-19/historical/{country}?lastdays={days}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Save raw JSON
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(RAW_DIR / f"{ts}_covid_{country}.json", "w") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        print(f"API error: {e}")
        return None

# ------------------- Transformation -------------------
def transform_to_df(raw_data, country):
    timeline = raw_data.get("timeline", {})
    cases = timeline.get("cases", {})
    deaths = timeline.get("deaths", {})
    recovered = timeline.get("recovered", {})
    
    rows = []
    for date in cases.keys():
        rows.append({
            "date": pd.to_datetime(date),
            "country": country,
            "total_cases": cases.get(date, 0),
            "total_deaths": deaths.get(date, 0),
            "total_recovered": recovered.get(date, 0)
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("date")
    df["new_cases"] = df["total_cases"].diff().fillna(0)
    df["new_cases_ma7"] = df["new_cases"].rolling(window=7, min_periods=1).mean()
    return df

# ------------------- Data Quality -------------------
def quality_checks(df):
    report = {}
    # Missing date gaps (>1 day)
    gaps = (df["date"].diff().dt.days > 1).sum()
    report["missing_date_gaps"] = gaps
    # Negative new cases
    neg = (df["new_cases"] < 0).sum()
    report["negative_new_cases"] = neg
    # Outliers ( > 3 std)
    mean = df["new_cases"].mean()
    std = df["new_cases"].std()
    outliers = (df["new_cases"] > mean + 3*std).sum() if std > 0 else 0
    report["outlier_days"] = outliers
    # Score 0-100
    score = 100
    if gaps > 0: score -= min(20, gaps*5)
    if neg > 0: score -= 30
    if outliers > 5: score -= 20
    report["quality_score"] = max(0, score)
    return report

# ------------------- Main -------------------
def main():
    print("=== Healthcare ETL ===")
    country = "USA"
    raw = fetch_covid_data(country, days=60)
    if not raw:
        return
    df = transform_to_df(raw, country)
    df.to_csv(PROCESSED_DIR / "covid_data.csv", index=False)
    report = quality_checks(df)
    with open(PROCESSED_DIR / "quality_report.json", "w") as f:
        json.dump(report, f)
    print(f"✅ Saved {len(df)} rows. Quality score: {report['quality_score']}/100")

if __name__ == "__main__":
    main()
