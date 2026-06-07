# Healthcare Dashboard – COVID‑19 Trends

## Run steps (exactly as required)

```bash
# 1. Unzip the folder
# 2. Open terminal inside healthcare-dashboard/

python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
python etl.py
streamlit run app.py
