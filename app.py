"""
StockLens V3 — Streamlit Edition
A comprehensive financial dashboard for thematic stock research and analysis.
Single-file application: fetches data, calculates indicators, renders dashboard.

Deployment bump: 2026-04-09 (force Streamlit Cloud rebuild)
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import numpy as np

# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="StockLens",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CUSTOM CSS — Dark Financial Terminal Theme
# ============================================================

st.markdown("""
<style>
    :root {
        --bg-primary: #0A0B0F;
        --bg-secondary: #141720;
        --bg-tertiary: #1E2238;
        --bg-card: #252A3F;

        --text-primary: #FFFFFF;
        --text-secondary: #B4BCD0;
        --text-muted: #6B7280;

        --accent-purple: #8B5CF6;
        --accent-blue: #3B82F6;
        --accent-green: #10B981;
        --accent-red: #EF4444;
        --accent-yellow: #F59E0B;
        --accent-orange: #F97316;

        --border-primary: #374151;
        --border-secondary: #4B5563;
    }

    /* App background (V2 exact gradient) */
    .stApp,
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0A0B0F 0%, #141720 50%, #1E2238 100%);
        color: var(--text-primary);
    }

    /* Improve default text colors */
    .stMarkdown, .stText, .stCaption, .stSubheader, .stHeader, .stTitle,
    label, p, span, div {
        color: var(--text-primary);
    }
    .stCaption { color: var(--text-secondary) !important; }

    /* Tab styling (V2 purple accent) */
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: var(--bg-secondary);
        color: var(--text-secondary);
        border: 1px solid var(--border-primary);
        border-radius: 8px;
        padding: 10px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--accent-purple);
        color: var(--text-primary);
        border: 1px solid rgba(139, 92, 246, 0.55);
        font-weight: 700;
    }

    /* Metric card styling */
    [data-testid="metric-container"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-primary);
        border-radius: 10px;
        padding: 12px;
        box-shadow: 0 0 0 1px rgba(0,0,0,0.15);
    }

    /* Dataframe / table styling */
    div[data-testid="stDataFrame"] {
        background-color: var(--bg-tertiary);
        border: 1px solid var(--border-primary);
        border-radius: 12px;
        padding: 6px;
    }
    div[data-testid="stDataFrame"] table {
        color: var(--text-secondary) !important;
    }
    div[data-testid="stDataFrame"] thead tr th {
        background-color: var(--bg-secondary) !important;
        /* Teal header text to match old dashboard */
        color: #14B8A6 !important;
        border-bottom: 1px solid var(--border-primary) !important;
    }
    div[data-testid="stDataFrame"] tbody tr td {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-secondary) !important;
        border-bottom: 1px solid rgba(55, 65, 81, 0.65) !important;
    }
    div[data-testid="stDataFrame"] tbody tr:hover td {
        background-color: var(--bg-card) !important;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Legend styling */
    .legend-text {
        font-size: 13px;
        line-height: 1.8;
        margin-top: 10px;
        padding: 12px;
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-primary);
        border-radius: 10px;
        color: var(--text-secondary);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CURRENCY MAPPING
# ============================================================

def get_currency_symbol(symbol):
    """Map ticker suffix to currency symbol."""
    if '.T' in symbol or '.KS' in symbol or '.TT' in symbol:
        if '.T' in symbol: return '¥'
        if '.KS' in symbol: return '₩'
        if '.TT' in symbol: return 'NT$'
    elif '.PA' in symbol or '.DE' in symbol or '.AS' in symbol or '.MI' in symbol:
        return '€'
    elif '.L' in symbol:
        return '£'
    elif '.AX' in symbol:
        return 'A$'
    elif '.NS' in symbol:
        return '₹'
    elif '.CO' in symbol:
        return 'kr'
    return '$'

def format_price(price, symbol):
    """Format price with correct currency symbol."""
    if price is None or pd.isna(price):
        return "—"
    curr = get_currency_symbol(symbol)
    if curr == '¥' or curr == '₩':
        return f"{curr} {price:,.0f}"
    return f"{curr} {price:,.2f}"

# ============================================================
# DATA FETCHING
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol, period="1y"):
    """Fetch OHLCV data for a single stock from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if df.empty:
            return None, f"No data returned"
        return df, None
    except Exception as e:
        return None, str(e)

def fetch_all_with_validation(stock_list, max_retries=3):
    """Fetch all stocks with validation and retry logic."""
    results = {}
    all_failures = []

    # Progress tracking
    progress_bar = st.progress(0, text="Fetching stock data...")
    total = len(stock_list)

    # Initial fetch
    for idx, (_, row) in enumerate(stock_list.iterrows()):
        symbol = row['symbol']
        progress_bar.progress((idx + 1) / total, text=f"Fetching {symbol}... ({idx+1}/{total})")
        df, error = fetch_stock_data(symbol)
        if df is not None and len(df) > 0:
            results[symbol] = {'data': df, **row.to_dict()}
        else:
            all_failures.append({'symbol': symbol, 'error': error, 'attempt': 1})

    # Retry loop
    for attempt in range(2, max_retries + 1):
        if not all_failures:
            break
        progress_bar.progress(0.95, text=f"Retrying {len(all_failures)} failed stocks (attempt {attempt})...")
        remaining_failures = []
        for fail in all_failures:
            time.sleep(0.5)
            df, error = fetch_stock_data(fail['symbol'])
            if df is not None and len(df) > 0:
                row = stock_list[stock_list['symbol'] == fail['symbol']].iloc[0]
                results[fail['symbol']] = {'data': df, **row.to_dict()}
            else:
                remaining_failures.append({
                    'symbol': fail['symbol'],
                    'error': error,
                    'attempt': attempt
                })
        all_failures = remaining_failures

    progress_bar.progress(1.0, text=f"Done! Loaded {len(results)}/{total} stocks.")
    time.sleep(0.5)
    progress_bar.empty()

    return results, all_failures

# ============================================================
# TECHNICAL INDICATOR CALCULATIONS
# ============================================================

def calculate_indicators(df):
    """Calculate all technical indicators for a stock (pure pandas/numpy).

    This replaces the prior pandas-ta implementation for Python 3.14 compatibility.
    Column names are kept identical to the pandas-ta defaults used elsewhere in the app.
    """
    try:
        close = df['Close']

        # ----------------------------
        # RSI (14)
        # Wilder-style smoothing (matches common RSI implementations closely)
        # ----------------------------
        length = 14
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
        avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # ----------------------------
        # MACD (12, 26, 9)
        # pandas-ta column names: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        # ----------------------------
        ema_fast = close.ewm(span=12, adjust=False, min_periods=12).mean()
        ema_slow = close.ewm(span=26, adjust=False, min_periods=26).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False, min_periods=9).mean()
        hist = macd_line - signal_line

        df['MACD_12_26_9'] = macd_line
        df['MACDs_12_26_9'] = signal_line
        df['MACDh_12_26_9'] = hist

        # ----------------------------
        # Simple Moving Averages (50, 200)
        # ----------------------------
        df['SMA_50'] = close.rolling(window=50, min_periods=50).mean()
        df['SMA_200'] = close.rolling(window=200, min_periods=200).mean()

        # 200 DMA slope (over last 10 days)
        df['SMA_200_slope'] = df['SMA_200'].diff(10)
    except Exception:
        pass

    return df

def classify_trend(price, sma50, sma200):
    """Classify trend based on price vs DMAs."""
    if price is None or pd.isna(price) or sma50 is None or pd.isna(sma50) or sma200 is None or pd.isna(sma200):
        return 'N/A'
    if price > sma50 and price > sma200:
        return 'Bullish'
    elif price < sma50 and price < sma200:
        return 'Bearish'
    return 'Neutral'

def classify_macd(macd_val, signal_val):
    """Classify MACD signal."""
    if pd.isna(macd_val) or pd.isna(signal_val):
        return 'N/A'
    return 'Bullish' if macd_val > signal_val else 'Bearish'

# ============================================================
# BUILD SCORECARD TABLE
# ============================================================

def build_scorecard(results, theme_stocks):
    """Build the summary scorecard dataframe for a theme."""
    rows = []
    for _, stock_row in theme_stocks.iterrows():
        symbol = stock_row['symbol']
        if symbol not in results:
            continue

        stock_data = results[symbol]
        df = stock_data['data'].copy()

        # Calculate indicators
        df = calculate_indicators(df)

        if len(df) < 2:
            continue

        latest = df.iloc[-1]

        def _last_valid(series):
            s = series.dropna()
            return s.iloc[-1] if not s.empty else None

        def _valid_or_none(v):
            return None if v is None or pd.isna(v) else v

        # ----------------------------
        # Price (NaN-safe)
        # Some international tickers can have the latest row partially filled
        # (e.g., Close=NaN during partial sessions). Fall back to last valid close.
        # ----------------------------
        close_series = df['Close'] if 'Close' in df.columns else pd.Series(dtype=float)
        price = latest.get('Close', None)
        if price is None or pd.isna(price):
            price = _last_valid(close_series)
        price = _valid_or_none(price)

        # ----------------------------
        # 12M return (NaN-safe)
        # Prefer the close ~252 trading days ago from the *valid* close series.
        # ----------------------------
        valid_closes = close_series.dropna()
        price_1y = None
        if not valid_closes.empty:
            if len(valid_closes) >= 252:
                price_1y = valid_closes.iloc[-252]
            else:
                price_1y = valid_closes.iloc[0]
        price_1y = _valid_or_none(price_1y)

        if price is not None and price_1y is not None and price_1y > 0:
            ret_12m = ((price / price_1y) - 1) * 100
        else:
            ret_12m = None

        # RSI (NaN-safe)
        rsi = _valid_or_none(latest.get('RSI_14', None))

        # Trend (NaN-safe)
        sma50 = _valid_or_none(latest.get('SMA_50', None))
        sma200 = _valid_or_none(latest.get('SMA_200', None))
        trend = classify_trend(price, sma50, sma200) if price is not None else 'N/A'

        # vs 50DMA / 200DMA (NaN-safe)
        vs_50 = ((price / sma50) - 1) * 100 if price is not None and sma50 is not None and sma50 > 0 else None
        vs_200 = ((price / sma200) - 1) * 100 if price is not None and sma200 is not None and sma200 > 0 else None

        # 200 DMA direction
        sma200_slope = _valid_or_none(latest.get('SMA_200_slope', None))
        if sma200_slope is not None:
            dir_200 = '▲' if sma200_slope > 0 else '▼'
        else:
            dir_200 = '—'

        # Distance from 52-week high (NaN-safe)
        high_series = df['High'] if 'High' in df.columns else pd.Series(dtype=float)
        high_window = high_series.dropna().tail(252) if len(df) >= 252 else high_series.dropna()
        high_52w = high_window.max() if not high_window.empty else None
        high_52w = _valid_or_none(high_52w)

        if price is not None and high_52w is not None and high_52w > 0:
            dist_52wh = ((price / high_52w) - 1) * 100
        else:
            dist_52wh = None

        # MACD signal (NaN-safe)
        macd_val = _valid_or_none(latest.get('MACD_12_26_9', None))
        macd_signal = _valid_or_none(latest.get('MACDs_12_26_9', None))
        macd_class = classify_macd(macd_val, macd_signal)

        # Volume vs average (NaN-safe)
        vol_series = df['Volume'] if 'Volume' in df.columns else pd.Series(dtype=float)
        vol_current = latest.get('Volume', None)
        if vol_current is None or pd.isna(vol_current):
            vol_current = _last_valid(vol_series)
        vol_current = _valid_or_none(vol_current)

        vol_avg_series = vol_series.dropna().tail(20)
        vol_avg = vol_avg_series.mean() if not vol_avg_series.empty else None
        vol_avg = _valid_or_none(vol_avg)

        if vol_current is None or vol_avg is None:
            vol_vs_avg = 'N/A'
        else:
            vol_vs_avg = 'Above' if vol_current > vol_avg else 'Below'

        rows.append({
            'Ticker': symbol,
            'Company': stock_data.get('name', ''),
            'Country': stock_data.get('country', ''),
            'Subsector': stock_data.get('subsector', ''),
            'Last Price': price,
            '12M Ret': ret_12m,
            'RSI(14)': rsi,
            'Trend': trend,
            'vs 50DMA': vs_50,
            'vs 200DMA': vs_200,
            '200 Dir': dir_200,
            'Dist 52WH': dist_52wh,
            'MACD Sig': macd_class,
            'Vol vs Avg': vol_vs_avg,
            '_symbol': symbol,  # Hidden column for currency formatting
        })

    scorecard = pd.DataFrame(rows)
    if len(scorecard) > 0:
        scorecard = scorecard.sort_values('12M Ret', ascending=False)
    return scorecard

# ============================================================
# COLOR STYLING FUNCTIONS
# ============================================================

def style_scorecard(df):
    """Apply color coding to the scorecard dataframe.

    Note: upstream code formats `Last Price` into a currency string (e.g. "$123.45").
    Pandas Styler's numeric formatters will raise if they receive strings, so we
    explicitly coerce numeric columns and avoid re-formatting `Last Price`.
    """
    display_df = df.drop(columns=['_symbol'], errors='ignore').copy()

    # Coerce numeric columns defensively (prevents Styler formatter errors)
    numeric_cols = ['12M Ret', 'RSI(14)', 'vs 50DMA', 'vs 200DMA', 'Dist 52WH']
    for c in numeric_cols:
        if c in display_df.columns:
            display_df[c] = pd.to_numeric(display_df[c], errors='coerce')

    def color_rsi(val):
        if pd.isna(val): return ''
        if val < 30: return 'color: #10B981'
        if val > 70: return 'color: #EF4444'
        return 'color: #F59E0B'

    def color_trend(val):
        if val == 'Bullish': return 'color: #10B981'
        if val == 'Bearish': return 'color: #EF4444'
        if val == 'Neutral': return 'color: #F59E0B'
        return ''

    def color_pct(val):
        if pd.isna(val): return ''
        try:
            v = float(val)
            return 'color: #10B981' if v > 0 else 'color: #EF4444'
        except (ValueError, TypeError):
            return ''

    def color_dist52(val):
        if pd.isna(val): return ''
        try:
            v = float(val)
            if v > -10: return 'color: #10B981'
            if v > -20: return 'color: #F59E0B'
            return 'color: #EF4444'
        except (ValueError, TypeError):
            return ''

    def color_dir(val):
        if val == '▲': return 'color: #10B981'
        if val == '▼': return 'color: #EF4444'
        return ''

    def color_vol(val):
        if val == 'Above': return 'color: #10B981'
        if val == 'Below': return 'color: #EF4444'
        return ''

    styled = display_df.style

    # Base table styling (ensures muted text + theme background even when Streamlit
    # overrides global CSS)
    styled = styled.set_properties(**{
        "color": "#B4BCD0",
        "background-color": "#141720",
    })
    styled = styled.set_table_styles([
        {
            "selector": "th",
            "props": [
                ("color", "#14B8A6"),
                ("background-color", "#141720"),
                ("border-bottom", "1px solid rgba(180, 188, 208, 0.15)"),
            ],
        },
        {
            "selector": "td",
            "props": [
                ("border-bottom", "1px solid rgba(180, 188, 208, 0.08)"),
            ],
        },
    ], overwrite=False)

    # Apply per-column styling
    if 'RSI(14)' in display_df.columns:
        styled = styled.map(color_rsi, subset=['RSI(14)'])
    if 'Trend' in display_df.columns:
        styled = styled.map(color_trend, subset=['Trend'])
    if '12M Ret' in display_df.columns:
        styled = styled.map(color_pct, subset=['12M Ret'])
    if 'vs 50DMA' in display_df.columns:
        styled = styled.map(color_pct, subset=['vs 50DMA'])
    if 'vs 200DMA' in display_df.columns:
        styled = styled.map(color_pct, subset=['vs 200DMA'])
    if 'Dist 52WH' in display_df.columns:
        styled = styled.map(color_dist52, subset=['Dist 52WH'])
    if 'MACD Sig' in display_df.columns:
        styled = styled.map(color_trend, subset=['MACD Sig'])
    if '200 Dir' in display_df.columns:
        styled = styled.map(color_dir, subset=['200 Dir'])
    if 'Vol vs Avg' in display_df.columns:
        styled = styled.map(color_vol, subset=['Vol vs Avg'])

    # Number formatting
    styled = styled.format({
        # 'Last Price' is already a currency-formatted string upstream
        '12M Ret': '{:+.2f}%',
        'RSI(14)': '{:.1f}',
        'vs 50DMA': '{:+.2f}%',
        'vs 200DMA': '{:+.2f}%',
        'Dist 52WH': '{:.2f}%',
    }, na_rep='—')

    return styled

# ============================================================
# INDEX DASHBOARD — CHARTS & METRICS
# ============================================================

THEME_BENCHMARKS = {
    'Semiconductors': ['SOXX', 'SPY'],
    'Full Stack': ['QQQ', 'SPY'],
    'Power Energy': ['XLE', 'SPY'],
    'Fiber Optics': ['QQQ', 'SPY'],
    'Chemicals': ['XLB', 'SPY'],
    'Commodities': ['GLD', 'SPY'],
    'BTC Miners': ['IBIT', 'SPY'],
    'Other': ['SPY', 'QQQ'],
}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_benchmark(symbol, period="1y", ytd_start=None):
    """Fetch benchmark data."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if not df.empty:
            # Filter to YTD if specified
            if ytd_start is not None:
                # Convert ytd_start to match the timezone of the dataframe index
                if hasattr(df.index, 'tz') and df.index.tz is not None:
                    ytd_start_tz = ytd_start.tz_localize(df.index.tz)
                else:
                    ytd_start_tz = ytd_start.tz_localize(None) if ytd_start.tz is not None else ytd_start
                df = df[df.index >= ytd_start_tz]
            return df['Close']
    except Exception:
        pass
    return None

def calculate_theme_index(results, theme_stocks, time_period="12 Month"):
    """Calculate equal-weight normalized index for a theme."""
    all_prices = pd.DataFrame()
    
    # Determine YTD start date if needed
    ytd_start = None
    if time_period == "YTD":
        ytd_start = pd.Timestamp(datetime(datetime.now().year, 1, 1))
    
    for _, row in theme_stocks.iterrows():
        symbol = row['symbol']
        if symbol in results:
            prices = results[symbol]['data']['Close']
            
            # Filter to YTD if specified
            if ytd_start is not None:
                # Convert ytd_start to match the timezone of the price index
                if hasattr(prices.index, 'tz') and prices.index.tz is not None:
                    ytd_start_tz = ytd_start.tz_localize(prices.index.tz)
                else:
                    ytd_start_tz = ytd_start.tz_localize(None) if ytd_start.tz is not None else ytd_start
                prices = prices[prices.index >= ytd_start_tz]
            
            if len(prices) > 0:
                normalized = ((prices / prices.iloc[0]) - 1) * 100
                all_prices[symbol] = normalized

    if all_prices.empty:
        return None
    # Align dates and forward-fill
    all_prices = all_prices.dropna(how='all')
    ew_index = all_prices.mean(axis=1)
    return ew_index

def render_dashboard_view(results, stock_list):
    """Render the Index-Level Dashboard view."""
    st.markdown("## Index-Level Dashboard")

    themes = stock_list['theme'].unique().tolist()
    
    # Theme and Time Period selection
    col_theme, col_period = st.columns([3, 1])
    with col_theme:
        selected_theme = st.selectbox("Theme", themes, key="dash_theme")
    with col_period:
        time_period = st.selectbox("Period", ["12 Month", "YTD"], key="dash_period")

    theme_stocks = stock_list[stock_list['theme'] == selected_theme]
    ew_index = calculate_theme_index(results, theme_stocks, time_period)

    if ew_index is None or len(ew_index) == 0:
        st.warning("Not enough data to calculate theme index.")
        return

    # Determine YTD start date for benchmarks
    ytd_start = None
    if time_period == "YTD":
        ytd_start = pd.Timestamp(datetime(datetime.now().year, 1, 1))

    # Fetch benchmarks
    benchmarks = THEME_BENCHMARKS.get(selected_theme, ['SPY', 'QQQ'])
    bench_data = {}
    for bench_sym in benchmarks:
        bench_prices = fetch_benchmark(bench_sym, ytd_start=ytd_start)
        if bench_prices is not None and len(bench_prices) > 0:
            bench_normalized = ((bench_prices / bench_prices.iloc[0]) - 1) * 100
            bench_data[bench_sym] = bench_normalized

    # Build chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ew_index.index, y=ew_index.values,
        name=f'EW {selected_theme} Index',
        line=dict(color='#8B5CF6', width=2)
    ))

    # V2 palette for benchmark lines
    colors = ['#3B82F6', '#10B981', '#EF4444']
    for i, (bench_sym, bench_vals) in enumerate(bench_data.items()):
        fig.add_trace(go.Scatter(
            x=bench_vals.index, y=bench_vals.values,
            name=bench_sym,
            line=dict(color=colors[i % len(colors)], width=1.5)
        ))

    # Dynamic title based on time period
    period_label = "YTD" if time_period == "YTD" else "12 Month"
    fig.update_layout(
        template='plotly_dark',
        title=f'{selected_theme} Theme vs Benchmarks — {period_label} (Normalized to 0)',
        height=450,
        paper_bgcolor='#0A0B0F',
        plot_bgcolor='#141720',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Metric cards
    # Index now starts at 0, so the current value IS the percentage return
    index_level = ew_index.iloc[-1]
    period_return = index_level  # Already in percentage form since normalization is ((p/p0)-1)*100

    # Average RSI across theme (use only data within the selected period)
    rsi_values = []
    for _, row in theme_stocks.iterrows():
        if row['symbol'] in results:
            df = results[row['symbol']]['data'].copy()
            # Filter to selected period for RSI calculation
            if time_period == "YTD":
                ytd_start_dt = pd.Timestamp(datetime(datetime.now().year, 1, 1))
                # Handle timezone matching
                if hasattr(df.index, 'tz') and df.index.tz is not None:
                    ytd_start_dt = ytd_start_dt.tz_localize(df.index.tz)
                else:
                    ytd_start_dt = ytd_start_dt.tz_localize(None) if ytd_start_dt.tz is not None else ytd_start_dt
                df = df[df.index >= ytd_start_dt]
            df = calculate_indicators(df)
            rsi_val = df.iloc[-1].get('RSI_14', None)
            if rsi_val is not None and not pd.isna(rsi_val):
                rsi_values.append(rsi_val)
    avg_rsi = np.mean(rsi_values) if rsi_values else 0

    # Theme trend (majority vote) - use only data within selected period
    trends = []
    for _, row in theme_stocks.iterrows():
        if row['symbol'] in results:
            df = results[row['symbol']]['data'].copy()
            # Filter to selected period for trend calculation
            if time_period == "YTD":
                ytd_start_dt = pd.Timestamp(datetime(datetime.now().year, 1, 1))
                # Handle timezone matching
                if hasattr(df.index, 'tz') and df.index.tz is not None:
                    ytd_start_dt = ytd_start_dt.tz_localize(df.index.tz)
                else:
                    ytd_start_dt = ytd_start_dt.tz_localize(None) if ytd_start_dt.tz is not None else ytd_start_dt
                df = df[df.index >= ytd_start_dt]
            df = calculate_indicators(df)
            latest = df.iloc[-1]
            t = classify_trend(latest['Close'], latest.get('SMA_50'), latest.get('SMA_200'))
            trends.append(t)
    if trends:
        from collections import Counter
        trend_counts = Counter(trends)
        trend_status = trend_counts.most_common(1)[0][0]
    else:
        trend_status = 'N/A'

    # vs benchmark
    # Benchmark is also normalized to 0, so values are already percentage returns
    primary_bench = benchmarks[0] if benchmarks else 'SPY'
    if primary_bench in bench_data:
        bench_return = bench_data[primary_bench].iloc[-1]  # Already a percentage return
        vs_bench = period_return - bench_return
    else:
        vs_bench = 0
        bench_return = 0

    # Dynamic metric labels based on time period
    return_label = "YTD Return" if time_period == "YTD" else "12M Return"
    vs_label = f"vs {primary_bench} (YTD)" if time_period == "YTD" else f"vs {primary_bench} (12M)"

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("EW Index Return", f"{index_level:+.1f}%")
    col2.metric(return_label, f"{period_return:+.2f}%")
    col3.metric("RSI(14)", f"{avg_rsi:.1f}")
    col4.metric("Trend Status", trend_status)
    col5.metric(vs_label, f"{vs_bench:+.2f}%")

    # Dynamic narrative based on time period
    if time_period == "YTD":
        st.markdown(f"""
        The equal-weight {selected_theme.lower()} index has returned **{period_return:+.1f}%** year-to-date.
        This compares to {primary_bench} at **{bench_return:+.1f}%** over the same period.
        The overall trend is **{trend_status}** with an RSI of **{avg_rsi:.1f}**.
        """)
    else:
        st.markdown(f"""
        The equal-weight {selected_theme.lower()} index has returned **{period_return:+.1f}%** over the trailing 12 months.
        This compares to {primary_bench} at **{bench_return:+.1f}%** over the same period.
        The overall trend is **{trend_status}** with an RSI of **{avg_rsi:.1f}**.
        """)

# ============================================================
# LEGEND
# ============================================================

def render_legend():
    """Render the color-coded legend."""
    st.markdown("""
    <div class="legend-text">
    <strong>Sorted by twelve month_return, descending.</strong><br><br>
    <strong>RSI:</strong>
    <span style="color:#10B981">Green=Oversold(&lt;30)</span> •
    <span style="color:#F59E0B">Gold=Neutral(30-70)</span> •
    <span style="color:#EF4444">Red=Overbought(&gt;70)</span><br>
    <strong>Trend:</strong>
    <span style="color:#10B981">Green=Bullish(above all DMAs)</span> •
    <span style="color:#F59E0B">Gold=Neutral(mixed)</span> •
    <span style="color:#EF4444">Red=Bearish(below all DMAs)</span><br>
    <strong>Dist 52WH:</strong>
    <span style="color:#10B981">Green=Strong(&gt;-10%)</span> •
    <span style="color:#F59E0B">Gold=Pullback(-10% to -20%)</span> •
    <span style="color:#EF4444">Red=Correction(&lt;-20%)</span><br>
    <strong>Returns/DMAs:</strong>
    <span style="color:#10B981">Green=Positive/Above</span> •
    <span style="color:#EF4444">Red=Negative/Below</span>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# MAIN APP
# ============================================================

def main():
    # Header
    col_title, col_nav = st.columns([4, 1])
    with col_title:
        # Gold title to match V2 accent color
        st.markdown(
            '<h1 style="color:#F59E0B; margin-bottom: 0;">📊 StockLens</h1>',
            unsafe_allow_html=True,
        )
    with col_nav:
        view = st.selectbox("", ["Dashboard", "Trending"], label_visibility="collapsed")

    # Load stock list
    try:
        stock_list = pd.read_csv("stocks.csv")
    except FileNotFoundError:
        st.error("stocks.csv not found. Please ensure the file is in the repository root.")
        return

    # Sidebar — Data Status
    with st.sidebar:
        st.subheader("📡 Data Status")
        if st.button("🔄 Refresh All Data"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")

    # Fetch data
    results, failures = fetch_all_with_validation(stock_list)

    # Update sidebar with status
    with st.sidebar:
        total = len(stock_list)
        loaded = len(results)
        st.write(f"✅ Loaded: **{loaded}/{total}** stocks")
        if failures:
            st.warning(f"⚠️ {len(failures)} stocks failed:")
            for f in failures:
                st.write(f"  ❌ `{f['symbol']}`: {f.get('error', 'Unknown')}")
        st.write(f"🕐 Last refresh: {datetime.now().strftime('%b %d, %Y %I:%M %p')}")
        st.markdown("---")
        st.caption("StockLens © 2026")

    if not results:
        st.error("No stock data loaded. Check your internet connection and try refreshing.")
        return

    # ========== VIEW: STOCK TABLES ==========
    if view == "Dashboard":
        themes = stock_list['theme'].unique().tolist()
        tab_labels = [f"{theme}  {len(stock_list[stock_list['theme']==theme])}" for theme in themes]
        tabs = st.tabs(tab_labels)

        for i, theme in enumerate(themes):
            with tabs[i]:
                theme_stocks = stock_list[stock_list['theme'] == theme]
                n = len(theme_stocks)

                st.markdown(f"### Summary Scorecard — All {n} {theme} Stocks")
                st.caption(f"Last updated: {datetime.now().strftime('%b %d, %Y, %I:%M %p CDT')}")

                # Build scorecard
                scorecard = build_scorecard(results, theme_stocks)

                if len(scorecard) == 0:
                    st.warning(f"No data available for {theme} stocks.")
                    continue

                # Format the Last Price column with currency symbols
                price_formatted = []
                for _, row in scorecard.iterrows():
                    price_formatted.append(format_price(row['Last Price'], row['_symbol']))
                scorecard['Last Price'] = price_formatted

                # Style and display
                styled = style_scorecard(scorecard)
                # Calculate height to show all rows without internal scrollbar
                # 35px per row + 40px header, no max limit to eliminate scrollbar
                table_height = 40 + len(scorecard) * 35
                st.dataframe(
                    styled,
                    use_container_width=True,
                    height=table_height,
                    hide_index=True,
                    column_config={
                        # Left-aligned text columns
                        "Company": st.column_config.TextColumn(alignment="left"),
                        "Subsector": st.column_config.TextColumn(alignment="left"),

                        # Center-aligned text columns
                        "Ticker": st.column_config.TextColumn(alignment="center"),
                        "Country": st.column_config.TextColumn(alignment="center"),
                        "Trend": st.column_config.TextColumn(alignment="center"),
                        "200 Dir": st.column_config.TextColumn(alignment="center"),
                        "MACD Sig": st.column_config.TextColumn(alignment="center"),
                        "Vol vs Avg": st.column_config.TextColumn(alignment="center"),
                        "Last Price": st.column_config.TextColumn(alignment="center"),

                        # Center-aligned numeric columns
                        "12M Ret": st.column_config.NumberColumn(format="%.2f%%", alignment="center"),
                        "RSI(14)": st.column_config.NumberColumn(format="%.1f", alignment="center"),
                        "vs 50DMA": st.column_config.NumberColumn(format="%.2f%%", alignment="center"),
                        "vs 200DMA": st.column_config.NumberColumn(format="%.2f%%", alignment="center"),
                        "Dist 52WH": st.column_config.NumberColumn(format="%.2f%%", alignment="center"),
                    },
                )

                # Legend
                render_legend()
                st.caption(f"{theme} Theme | StockLens Dashboard | {datetime.now().strftime('%B %Y')}")

    # ========== VIEW: TRENDING ==========
    elif view == "Trending":
        render_dashboard_view(results, stock_list)

if __name__ == "__main__":
    main()
