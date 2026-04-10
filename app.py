"""
StockLens V3 — Streamlit Edition
A comprehensive financial dashboard for thematic stock research and analysis.
Single-file application: fetches data, calculates indicators, renders dashboard.
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
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
    /* Dark background */
    .stApp { background-color: #0E1117; }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1A1E2E;
        color: #FAFAFA;
        border-radius: 4px;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFD700;
        color: #0E1117;
        font-weight: bold;
    }

    /* Metric card styling */
    [data-testid="metric-container"] {
        background-color: #1A1E2E;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 10px;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Legend styling */
    .legend-text {
        font-size: 13px;
        line-height: 1.8;
        margin-top: 10px;
        padding: 10px;
        background-color: #1A1E2E;
        border-radius: 6px;
    }

    /* Refresh button — make it prominent on main page */
    div[data-testid="stButton"] > button[kind="primary"] {
        background-color: #FFD700;
        color: #0E1117;
        font-weight: bold;
        border: none;
        padding: 10px 24px;
        font-size: 15px;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background-color: #FFC700;
        color: #0E1117;
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
    curr = get_currency_symbol(symbol)
    if curr == '¥' or curr == '₩':
        return f"{curr} {price:,.0f}"
    return f"{curr} {price:,.2f}"

# ============================================================
# DATA FETCHING
# ============================================================
# NOTE: Data fetching is now manual-only via the Refresh button.
# Results are stored in st.session_state and persist across ALL interactions
# (tab changes, dropdown changes, theme toggles, URL refreshes in the same
# browser session). The cache decorators have been REMOVED so that data is
# only ever fetched when the user explicitly clicks Refresh Data.

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
    """Fetch all stocks with validation and retry logic.
    Called ONLY when the user clicks the Refresh Data button."""
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


def fetch_benchmark(symbol, period="1y", ytd_start=None):
    """Fetch benchmark data. Called only during a full refresh."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if not df.empty:
            if ytd_start is not None:
                df = df[df.index >= ytd_start]
            return df['Close']
    except Exception:
        pass
    return None


def fetch_all_benchmarks(themes):
    """Pre-fetch all benchmark symbols referenced by the themes.
    Called once during a full refresh so tab/dropdown changes don't re-hit the network."""
    wanted = set()
    for theme in themes:
        for sym in THEME_BENCHMARKS.get(theme, ['SPY', 'QQQ']):
            wanted.add(sym)
    bench_store = {}
    for sym in wanted:
        prices = fetch_benchmark(sym)
        if prices is not None:
            bench_store[sym] = prices
    return bench_store


def run_full_refresh(stock_list):
    """Perform a full data refresh: stocks + benchmarks.
    Stores everything in session_state so it persists across reruns."""
    themes = stock_list['theme'].unique().tolist()
    results, failures = fetch_all_with_validation(stock_list)
    bench_store = fetch_all_benchmarks(themes)

    st.session_state['stock_results'] = results
    st.session_state['stock_failures'] = failures
    st.session_state['benchmark_store'] = bench_store
    st.session_state['last_refresh'] = datetime.now()
    st.session_state['data_loaded'] = True


# ============================================================
# TECHNICAL INDICATOR CALCULATIONS
# ============================================================
def calculate_indicators(df):
    """Calculate all technical indicators for a stock using pandas-ta."""
    try:
        rsi = df.ta.rsi(length=14)
        if rsi is not None:
            df['RSI_14'] = rsi
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None:
            df = pd.concat([df, macd], axis=1)
        sma50 = df.ta.sma(length=50)
        if sma50 is not None:
            df['SMA_50'] = sma50
        sma200 = df.ta.sma(length=200)
        if sma200 is not None:
            df['SMA_200'] = sma200
        if 'SMA_200' in df.columns:
            df['SMA_200_slope'] = df['SMA_200'].diff(10)
    except Exception:
        pass
    return df

def classify_trend(price, sma50, sma200):
    """Classify trend based on price vs DMAs."""
    if pd.isna(sma50) or pd.isna(sma200):
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
        df = calculate_indicators(df)
        if len(df) < 2:
            continue
        latest = df.iloc[-1]
        price = latest['Close']
        if len(df) >= 252:
            price_1y = df.iloc[-252]['Close']
        else:
            price_1y = df.iloc[0]['Close']
        ret_12m = ((price / price_1y) - 1) * 100 if price_1y > 0 else 0
        rsi = latest.get('RSI_14', None)
        sma50 = latest.get('SMA_50', None)
        sma200 = latest.get('SMA_200', None)
        trend = classify_trend(price, sma50, sma200)
        vs_50 = ((price / sma50) - 1) * 100 if sma50 and not pd.isna(sma50) and sma50 > 0 else None
        vs_200 = ((price / sma200) - 1) * 100 if sma200 and not pd.isna(sma200) and sma200 > 0 else None
        sma200_slope = latest.get('SMA_200_slope', None)
        if sma200_slope is not None and not pd.isna(sma200_slope):
            dir_200 = '▲' if sma200_slope > 0 else '▼'
        else:
            dir_200 = '—'
        high_52w = df['High'].tail(252).max() if len(df) >= 252 else df['High'].max()
        dist_52wh = ((price / high_52w) - 1) * 100 if high_52w > 0 else 0
        macd_val = latest.get('MACD_12_26_9', None)
        macd_signal = latest.get('MACDs_12_26_9', None)
        macd_class = classify_macd(macd_val, macd_signal)
        vol_current = latest.get('Volume', 0)
        vol_avg = df['Volume'].tail(20).mean() if 'Volume' in df.columns else 0
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
            '_symbol': symbol,
        })

    scorecard = pd.DataFrame(rows)
    if len(scorecard) > 0:
        scorecard = scorecard.sort_values('12M Ret', ascending=False)
    return scorecard

# ============================================================
# COLOR STYLING FUNCTIONS
# ============================================================
def style_scorecard(df):
    """Apply color coding to the scorecard dataframe."""
    display_df = df.drop(columns=['_symbol'], errors='ignore').copy()

    def color_rsi(val):
        if pd.isna(val): return ''
        if val < 30: return 'color: #00FF00'
        if val > 70: return 'color: #FF4444'
        return 'color: #FFD700'

    def color_trend(val):
        if val == 'Bullish': return 'color: #00FF00'
        if val == 'Bearish': return 'color: #FF4444'
        if val == 'Neutral': return 'color: #FFD700'
        return ''

    def color_pct(val):
        if pd.isna(val): return ''
        try:
            v = float(val)
            return 'color: #00FF00' if v > 0 else 'color: #FF4444'
        except (ValueError, TypeError):
            return ''

    def color_dist52(val):
        if pd.isna(val): return ''
        try:
            v = float(val)
            if v > -10: return 'color: #00FF00'
            if v > -20: return 'color: #FFD700'
            return 'color: #FF4444'
        except (ValueError, TypeError):
            return ''

    def color_dir(val):
        if val == '▲': return 'color: #00FF00'
        if val == '▼': return 'color: #FF4444'
        return ''

    def color_vol(val):
        if val == 'Above': return 'color: #00FF00'
        if val == 'Below': return 'color: #FF4444'
        return ''

    styled = display_df.style

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

    styled = styled.format({
        'Last Price': '{:.2f}',
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


def get_benchmark_series(symbol, ytd_start=None):
    """Read a benchmark from session_state (no network call).
    If YTD filtering is requested, it is applied in-memory to the cached series."""
    store = st.session_state.get('benchmark_store', {})
    series = store.get(symbol)
    if series is None:
        return None
    if ytd_start is not None:
        series = series[series.index >= ytd_start]
    return series


def calculate_theme_index(results, theme_stocks, time_period="12 Month"):
    """Calculate equal-weight normalized index for a theme."""
    all_prices = pd.DataFrame()
    ytd_start = None
    if time_period == "YTD":
        ytd_start = pd.Timestamp(datetime(datetime.now().year, 1, 1))
    for _, row in theme_stocks.iterrows():
        symbol = row['symbol']
        if symbol in results:
            prices = results[symbol]['data']['Close']
            if ytd_start is not None:
                prices = prices[prices.index >= ytd_start]
            if len(prices) > 0:
                normalized = ((prices / prices.iloc[0]) - 1) * 100
                all_prices[symbol] = normalized
    if all_prices.empty:
        return None
    all_prices = all_prices.dropna(how='all')
    ew_index = all_prices.mean(axis=1)
    return ew_index

def render_dashboard_view(results, stock_list):
    """Render the Index-Level Dashboard view."""
    st.markdown("## Index-Level Dashboard")

    themes = stock_list['theme'].unique().tolist()

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

    ytd_start = None
    if time_period == "YTD":
        ytd_start = pd.Timestamp(datetime(datetime.now().year, 1, 1))

    # Read benchmarks from session_state — NO network call
    benchmarks = THEME_BENCHMARKS.get(selected_theme, ['SPY', 'QQQ'])
    bench_data = {}
    for bench_sym in benchmarks:
        bench_prices = get_benchmark_series(bench_sym, ytd_start=ytd_start)
        if bench_prices is not None and len(bench_prices) > 0:
            bench_normalized = ((bench_prices / bench_prices.iloc[0]) - 1) * 100
            bench_data[bench_sym] = bench_normalized

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ew_index.index, y=ew_index.values,
        name=f'EW {selected_theme} Index',
        line=dict(color='#FFD700', width=2)
    ))

    colors = ['#4169E1', '#9370DB', '#FF6B6B']
    for i, (bench_sym, bench_vals) in enumerate(bench_data.items()):
        fig.add_trace(go.Scatter(
            x=bench_vals.index, y=bench_vals.values,
            name=bench_sym,
            line=dict(color=colors[i % len(colors)], width=1.5)
        ))

    period_label = "YTD" if time_period == "YTD" else "12 Month"
    fig.update_layout(
        template='plotly_dark',
        title=f'{selected_theme} Theme vs Benchmarks — {period_label} (Normalized to 0)',
        height=450,
        paper_bgcolor='#0E1117',
        plot_bgcolor='#0E1117',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    index_level = ew_index.iloc[-1]
    period_return = index_level

    rsi_values = []
    for _, row in theme_stocks.iterrows():
        if row['symbol'] in results:
            df = results[row['symbol']]['data'].copy()
            if time_period == "YTD":
                ytd_start_dt = datetime(datetime.now().year, 1, 1)
                df = df[df.index >= ytd_start_dt]
            df = calculate_indicators(df)
            rsi_val = df.iloc[-1].get('RSI_14', None)
            if rsi_val is not None and not pd.isna(rsi_val):
                rsi_values.append(rsi_val)
    avg_rsi = np.mean(rsi_values) if rsi_values else 0

    trends = []
    for _, row in theme_stocks.iterrows():
        if row['symbol'] in results:
            df = results[row['symbol']]['data'].copy()
            if time_period == "YTD":
                ytd_start_dt = datetime(datetime.now().year, 1, 1)
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

    primary_bench = benchmarks[0] if benchmarks else 'SPY'
    if primary_bench in bench_data:
        bench_return = bench_data[primary_bench].iloc[-1]
        vs_bench = period_return - bench_return
    else:
        vs_bench = 0
        bench_return = 0

    return_label = "YTD Return" if time_period == "YTD" else "12M Return"
    vs_label = f"vs {primary_bench} (YTD)" if time_period == "YTD" else f"vs {primary_bench} (12M)"

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("EW Index Return", f"{index_level:+.1f}%")
    col2.metric(return_label, f"{period_return:+.2f}%")
    col3.metric("RSI(14)", f"{avg_rsi:.1f}")
    col4.metric("Trend Status", trend_status)
    col5.metric(vs_label, f"{vs_bench:+.2f}%")

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
        <span style="color:#00FF00">Green=Oversold(&lt;30)</span> •
        <span style="color:#FFD700">Gold=Neutral(30-70)</span> •
        <span style="color:#FF4444">Red=Overbought(&gt;70)</span><br>
        <strong>Trend:</strong>
        <span style="color:#00FF00">Green=Bullish(above all DMAs)</span> •
        <span style="color:#FFD700">Gold=Neutral(mixed)</span> •
        <span style="color:#FF4444">Red=Bearish(below all DMAs)</span><br>
        <strong>Dist 52WH:</strong>
        <span style="color:#00FF00">Green=Strong(&gt;-10%)</span> •
        <span style="color:#FFD700">Gold=Pullback(-10% to -20%)</span> •
        <span style="color:#FF4444">Red=Correction(&lt;-20%)</span><br>
        <strong>Returns/DMAs:</strong>
        <span style="color:#00FF00">Green=Positive/Above</span> •
        <span style="color:#FF4444">Red=Negative/Below</span>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# MAIN APP
# ============================================================
def main():
    # --- Header row: title + view selector ---
    col_title, col_nav = st.columns([4, 1])
    with col_title:
        st.markdown("# 📊 StockLens")
    with col_nav:
        view = st.selectbox("", ["Dashboard", "Trending"], label_visibility="collapsed")

    # --- Load stock list (cheap, no network) ---
    try:
        stock_list = pd.read_csv("stocks.csv")
    except FileNotFoundError:
        st.error("stocks.csv not found. Please ensure the file is in the repository root.")
        return

    # --- Initialize session state keys on first run ---
    if 'data_loaded' not in st.session_state:
        st.session_state['data_loaded'] = False
        st.session_state['stock_results'] = {}
        st.session_state['stock_failures'] = []
        st.session_state['benchmark_store'] = {}
        st.session_state['last_refresh'] = None

    # --- PROMINENT DATA REFRESH CONTROL BAR (main page) ---
    # This is the ONLY way data gets refreshed. Tab changes, dropdown
    # changes, theme toggles, and URL refreshes all read from session_state.
    refresh_col1, refresh_col2, refresh_col3 = st.columns([1.3, 2.5, 2.2])
    with refresh_col1:
        refresh_clicked = st.button(
            "🔄 Refresh Data",
            type="primary",
            use_container_width=True,
            help="Fetch latest prices from Yahoo Finance. Data stays frozen until you click this again."
        )
    with refresh_col2:
        if st.session_state['last_refresh']:
            ts = st.session_state['last_refresh'].strftime('%b %d, %Y %I:%M %p')
            st.markdown(
                f"<div style='padding-top:8px;color:#888;'>"
                f"🕐 Last refresh: <strong style='color:#FAFAFA;'>{ts}</strong>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                "<div style='padding-top:8px;color:#FFD700;'>"
                "⚠️ No data loaded yet — click Refresh Data to fetch prices"
                "</div>",
                unsafe_allow_html=True
            )
    with refresh_col3:
        if st.session_state['data_loaded']:
            total = len(stock_list)
            loaded = len(st.session_state['stock_results'])
            fail_count = len(st.session_state['stock_failures'])
            status_color = '#00FF00' if fail_count == 0 else '#FFD700'
            st.markdown(
                f"<div style='padding-top:8px;text-align:right;color:{status_color};'>"
                f"✅ Loaded: <strong>{loaded}/{total}</strong>"
                + (f" ({fail_count} failed)" if fail_count else "")
                + "</div>",
                unsafe_allow_html=True
            )

    st.markdown("---")

    # --- Handle refresh click: fetch data NOW, store in session_state ---
    if refresh_clicked:
        with st.spinner("Fetching stock data from Yahoo Finance..."):
            run_full_refresh(stock_list)
        st.rerun()

    # --- Sidebar status (read-only, no fetch trigger) ---
    with st.sidebar:
        st.subheader("📡 Data Status")
        if st.session_state['data_loaded']:
            total = len(stock_list)
            loaded = len(st.session_state['stock_results'])
            st.write(f"✅ Loaded: **{loaded}/{total}** stocks")
            if st.session_state['stock_failures']:
                st.warning(f"⚠️ {len(st.session_state['stock_failures'])} failed:")
                for f in st.session_state['stock_failures']:
                    st.write(f"  ❌ `{f['symbol']}`: {f.get('error', 'Unknown')}")
            if st.session_state['last_refresh']:
                st.write(f"🕐 {st.session_state['last_refresh'].strftime('%b %d, %Y %I:%M %p')}")
        else:
            st.info("No data loaded yet.\nClick **Refresh Data** on the main page.")
        st.markdown("---")
        st.caption("StockLens © 2026")

    # --- If no data has been fetched yet, stop here ---
    if not st.session_state['data_loaded'] or not st.session_state['stock_results']:
        st.info(
            "👆 **Click the `🔄 Refresh Data` button above to fetch the latest prices.** "
            "Once loaded, you can freely switch tabs, change themes, and toggle filters "
            "without triggering another data pull."
        )
        return

    # --- Read results from session_state for the rest of the render ---
    results = st.session_state['stock_results']

    # ========== VIEW: STOCK TABLES ==========
    if view == "Dashboard":
        themes = stock_list['theme'].unique().tolist()
        tab_labels = [f"{theme} {len(stock_list[stock_list['theme']==theme])}" for theme in themes]
        tabs = st.tabs(tab_labels)

        for i, theme in enumerate(themes):
            with tabs[i]:
                theme_stocks = stock_list[stock_list['theme'] == theme]
                n = len(theme_stocks)

                st.markdown(f"### Summary Scorecard — All {n} {theme} Stocks")
                last_ts = st.session_state['last_refresh'].strftime('%b %d, %Y, %I:%M %p CDT')
                st.caption(f"Data as of: {last_ts}")

                scorecard = build_scorecard(results, theme_stocks)

                if len(scorecard) == 0:
                    st.warning(f"No data available for {theme} stocks.")
                    continue

                price_formatted = []
                for _, row in scorecard.iterrows():
                    price_formatted.append(format_price(row['Last Price'], row['_symbol']))
                scorecard['Last Price'] = price_formatted

                styled = style_scorecard(scorecard)
                table_height = 40 + len(scorecard) * 35
                st.dataframe(
                    styled,
                    use_container_width=True,
                    height=table_height,
                    hide_index=True,
                )

                render_legend()
                st.caption(f"{theme} Theme | StockLens Dashboard | {datetime.now().strftime('%B %Y')}")

    # ========== VIEW: TRENDING ==========
    elif view == "Trending":
        render_dashboard_view(results, stock_list)


if __name__ == "__main__":
    main()
