# StockLens V3

StockLens V3 is a Streamlit app for quickly exploring and filtering a curated list of stocks.

## Features

- Browse a stock universe from `stocks.csv`
- Search / filter symbols and company names
- Interactive Streamlit UI
- Streamlit Cloud–friendly repo layout (includes `.streamlit/config.toml`)

## Run locally

1. **Clone the repo**

   ```bash
   git clone https://github.com/nunya007007/stocklens_v3.git
   cd stocklens_v3
   ```

2. **Create a virtual environment (recommended)**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the app**

   ```bash
   streamlit run app.py
   ```

The app will open in your browser.

## Deploy on Streamlit Cloud

1. Push this repository to GitHub (already set up).
2. In Streamlit Cloud, click **Create app**.
3. Select this repo: `nunya007007/stocklens_v3`.
4. Set the entry point to:
   - **Main file path:** `app.py`
5. Deploy.

Streamlit Cloud will automatically install `requirements.txt` and use `.streamlit/config.toml` for app configuration.
