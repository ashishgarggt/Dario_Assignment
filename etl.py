import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def fetch_covid_data(country, days=90):
    url = f"https://disease.sh/v3/covid-19/historical/{country}?lastdays={days}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Save raw
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(RAW_DIR / f"{ts}_{country}.json", "w") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        print(f"API error for {country}: {e}")
        return None

def transform_to_df(raw_data, country):
    timeline = raw_data.get("timeline", {})
    cases = timeline.get("cases", {})
    deaths = timeline.get("deaths", {})
    recovered = timeline.get("recovered", {})
    
    rows = []
    for date_str in cases.keys():
        parsed_date = pd.to_datetime(date_str, format="%m/%d/%y", errors='coerce')
        if pd.isna(parsed_date):
            parsed_date = pd.to_datetime(date_str)
        rows.append({
            "date": parsed_date,
            "country": country,
            "total_cases": cases.get(date_str, 0),
            "total_deaths": deaths.get(date_str, 0),
            "total_recovered": recovered.get(date_str, 0)
        })
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    df["new_cases"] = df["total_cases"].diff().fillna(0).clip(lower=0)
    df["new_deaths"] = df["total_deaths"].diff().fillna(0).clip(lower=0)
    df["new_cases_ma7"] = df["new_cases"].rolling(7, min_periods=1).mean()
    df["new_deaths_ma7"] = df["new_deaths"].rolling(7, min_periods=1).mean()
    return df

def quality_checks(df):
    gaps = (df["date"].diff().dt.days > 1).sum()
    neg_cases = (df["new_cases"] < 0).sum()
    neg_deaths = (df["new_deaths"] < 0).sum()
    mean_cases = df["new_cases"].mean()
    std_cases = df["new_cases"].std()
    outliers = (df["new_cases"] > mean_cases + 3*std_cases).sum() if std_cases > 0 else 0
    score = 100
    if gaps > 0: score -= min(20, gaps*5)
    if neg_cases + neg_deaths > 0: score -= 30
    if outliers > 5: score -= 20
    return {
        "missing_date_gaps": int(gaps),
        "negative_new_cases": int(neg_cases),
        "negative_new_deaths": int(neg_deaths),
        "outlier_days": int(outliers),
        "quality_score": max(0, score)
    }

def main(country="USA", days=90):
    print(f"Fetching data for {country}...")
    raw = fetch_covid_data(country, days)
    if not raw:
        return None
    df = transform_to_df(raw, country)
    report = quality_checks(df)
    df.to_csv(PROCESSED_DIR / f"{country}_data.csv", index=False)
    with open(PROCESSED_DIR / f"{country}_quality.json", "w") as f:
        json.dump(report, f)
    print(f"Saved {len(df)} rows for {country}. Quality: {report['quality_score']}/100")
    return df

if __name__ == "__main__":
    # Example: fetch USA
    main("USA", 90)
