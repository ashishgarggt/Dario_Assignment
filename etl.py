import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

# Create folders
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def fetch_covid_data(country="USA", days=60):
    """Fetch historical COVID data for a country. No API key needed."""
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

def transform_to_df(raw_data, country):
    """Convert the actual API response to a clean DataFrame."""
    timeline = raw_data.get("timeline", {})
    cases = timeline.get("cases", {})
    deaths = timeline.get("deaths", {})
    recovered = timeline.get("recovered", {})
    
    rows = []
    # The dates are keys like "2/8/23" -> parse flexibly
    for date_str in cases.keys():
        # Use pandas to parse MM/DD/YY – it will assume 2023 for '23'
        parsed_date = pd.to_datetime(date_str, format="%m/%d/%y", errors='coerce')
        if pd.isna(parsed_date):
            # fallback to infer
            parsed_date = pd.to_datetime(date_str)
        rows.append({
            "date": parsed_date,
            "country": country,
            "total_cases": cases.get(date_str, 0),
            "total_deaths": deaths.get(date_str, 0),
            "total_recovered": recovered.get(date_str, 0)
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)
    df["new_cases"] = df["total_cases"].diff().fillna(0)
    # Ensure new_cases is never negative (data glitch fix)
    df["new_cases"] = df["new_cases"].clip(lower=0)
    df["new_cases_ma7"] = df["new_cases"].rolling(window=7, min_periods=1).mean()
    return df

def quality_checks(df):
    """Simple quality report."""
    report = {}
    # Missing date gaps (>1 day)
    gaps = (df["date"].diff().dt.days > 1).sum()
    report["missing_date_gaps"] = int(gaps)
    # Negative new cases (should be zero after clipping)
    neg = (df["new_cases"] < 0).sum()
    report["negative_new_cases"] = int(neg)
    # Outliers (>3 std)
    mean = df["new_cases"].mean()
    std = df["new_cases"].std()
    outliers = (df["new_cases"] > mean + 3*std).sum() if std > 0 else 0
    report["outlier_days"] = int(outliers)
    # Quality score 0-100
    score = 100
    if gaps > 0:
        score -= min(20, gaps * 5)
    if neg > 0:
        score -= 30
    if outliers > 5:
        score -= 20
    report["quality_score"] = max(0, score)
    return report

def main():
    print("=== Healthcare ETL ===")
    country = "USA"
    raw = fetch_covid_data(country, days=60)
    if not raw:
        print("Failed to fetch data. Exiting.")
        return
    df = transform_to_df(raw, country)
    df.to_csv(PROCESSED_DIR / "covid_data.csv", index=False)
    report = quality_checks(df)
    with open(PROCESSED_DIR / "quality_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"✅ Saved {len(df)} rows. Quality score: {report['quality_score']}/100")
    print(f"   Date range: {df['date'].min().date()} to {df['date'].max().date()}")

if __name__ == "__main__":
    main()