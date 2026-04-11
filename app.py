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
    .stMarkdown, .stText, .stCaption, label, p, span, div {
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

    /* Dataframe / table styling
       NOTE: st.dataframe uses a React grid component that ignores most CSS table selectors.
       Header styling (text color, alignment) must be done via:
       1. .streamlit/config.toml (theme settings - limited control)
       2. Pandas Styler set_table_styles() with st.table() (full control, no interactivity)
       3. column_config in st.dataframe() (alignment only)
       
       Cell-level styling works via Pandas Styler .map() method.
       See RESEARCH_FINDINGS.md for detailed explanation.
    */
    div[data-testid="stDataFrame"] {
        background-color: var(--bg-tertiary);
        border: 1px solid var(--border-primary);
        border-radius: 12px;
        padding: 6px;
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
        
        # ----------------------------
        # ADX (14) - Average Directional Index
        # ----------------------------
        df['ADX_14'] = calculate_adx(df, period=14)
        
        # ----------------------------
        # Bollinger Band %B (20-period, 2 std)
        # ----------------------------
        df['BB_PctB_20'] = calculate_bollinger_pctb(df, period=20, std_dev=2)
        
        # ----------------------------
        # Golden/Death Cross Detection
        # ----------------------------
        df['Golden_Cross'] = calculate_golden_cross(df)
        
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


def calculate_adx(df, period=14):
    """
    Calculate Average Directional Index (ADX) with Wilder's smoothing.
    
    ADX measures trend strength regardless of direction.
    Returns: ADX series (0-100 scale)
    """
    try:
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        # True Range (TR)
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        # Wilder's smoothing
        alpha = 1 / period
        
        tr_smooth = tr.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
        plus_dm_smooth = plus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
        minus_dm_smooth = minus_dm.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
        
        # +DI and -DI
        plus_di = 100 * plus_dm_smooth / tr_smooth.replace(0, np.nan)
        minus_di = 100 * minus_dm_smooth / tr_smooth.replace(0, np.nan)
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
        
        return adx
    except Exception:
        return pd.Series(index=df.index, dtype=float)


def calculate_bollinger_pctb(df, period=20, std_dev=2):
    """
    Calculate Bollinger Band %B (percent bandwidth).
    
    %B = (Price - Lower Band) / (Upper Band - Lower Band)
    - %B > 1: Price above upper band
    - %B = 1: Price at upper band
    - %B = 0.5: Price at middle band (SMA)
    - %B = 0: Price at lower band
    - %B < 0: Price below lower band
    """
    try:
        close = df['Close']
        
        # Middle band (SMA)
        sma = close.rolling(window=period, min_periods=period).mean()
        
        # Standard deviation
        std = close.rolling(window=period, min_periods=period).std()
        
        # Upper and lower bands
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        # %B calculation
        band_width = upper_band - lower_band
        pct_b = (close - lower_band) / band_width.replace(0, np.nan)
        
        return pct_b
    except Exception:
        return pd.Series(index=df.index, dtype=float)


def calculate_golden_cross(df):
    """
    Detect Golden Cross and Death Cross patterns.
    
    Golden Cross: 50 SMA crosses above 200 SMA (bullish)
    Death Cross: 50 SMA crosses below 200 SMA (bearish)
    
    Returns: Series with values:
        1 = Golden Cross (bullish signal)
        -1 = Death Cross (bearish signal)
        0 = No cross
    """
    try:
        close = df['Close']
        
        # Calculate SMAs
        sma_50 = close.rolling(window=50, min_periods=50).mean()
        sma_200 = close.rolling(window=200, min_periods=200).mean()
        
        # Determine cross signals
        # Golden cross: SMA50 > SMA200 and previous day SMA50 <= SMA200
        # Death cross: SMA50 < SMA200 and previous day SMA50 >= SMA200
        
        sma_50_prev = sma_50.shift(1)
        sma_200_prev = sma_200.shift(1)
        
        golden_cross = (sma_50 > sma_200) & (sma_50_prev <= sma_200_prev)
        death_cross = (sma_50 < sma_200) & (sma_50_prev >= sma_200_prev)
        
        signal = pd.Series(0, index=df.index, dtype=int)
        signal[golden_cross] = 1
        signal[death_cross] = -1
        
        return signal
    except Exception:
        return pd.Series(0, index=df.index, dtype=int)


def calculate_composite_rating(df):
    """
    Calculate composite rating from 11 weighted technical indicators.
    
    Indicators and weights:
    1. Trend (Price vs 50/200 SMA) - 20%
    2. MACD Signal - 15%
    3. RSI Momentum - 15%
    4. ADX Trend Strength - 10%
    5. Bollinger %B Position - 10%
    6. Golden/Death Cross - 10%
    7. 12M Return - 10%
    8. Volume vs Average - 5%
    9. vs 50DMA - 5%
    10. vs 200DMA - 5%
    11. Distance from 52W High - 5%
    
    Returns: (rating_label, score, confluence_note)
        rating_label: 'Strong Buy', 'Buy', 'Neutral', 'Sell', 'Strong Sell'
        score: -100 to +100
        confluence_note: description of signal alignment
    """
    try:
        # DEBUG: Log dataframe info for troubleshooting
        # st.write(f"DEBUG: DataFrame shape={df.shape}, columns={list(df.columns)}")
        
        if len(df) < 50:  # Reduced from 200 to 50 days for better compatibility
            return ('Insufficient Data', 0, f'Need at least 50 days of data (have {len(df)})')
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # Helper to safely get values
        def safe_get(val, default=np.nan):
            if val is None or pd.isna(val):
                return default
            return val
        
        # Initialize score components
        scores = []
        weights = []
        bullish_count = 0
        bearish_count = 0
        
        # 1. Trend (Price vs 50/200 SMA) - 20%
        price = safe_get(latest.get('Close'))
        sma_50 = safe_get(latest.get('SMA_50'))
        sma_200 = safe_get(latest.get('SMA_200'))
        
        if not np.isnan(price) and not np.isnan(sma_50) and not np.isnan(sma_200):
            if price > sma_50 and price > sma_200 and sma_50 > sma_200:
                trend_score = 100  # Strong bullish
                bullish_count += 1
            elif price > sma_50 and price > sma_200:
                trend_score = 75   # Bullish
                bullish_count += 1
            elif price < sma_50 and price < sma_200 and sma_50 < sma_200:
                trend_score = -100  # Strong bearish
                bearish_count += 1
            elif price < sma_50 and price < sma_200:
                trend_score = -75   # Bearish
                bearish_count += 1
            else:
                trend_score = 0     # Neutral
            scores.append(trend_score)
            weights.append(20)
        
        # 2. MACD Signal - 15%
        macd = safe_get(latest.get('MACD_12_26_9'))
        macd_signal = safe_get(latest.get('MACDs_12_26_9'))
        macd_hist = safe_get(latest.get('MACDh_12_26_9'))
        macd_hist_prev = safe_get(prev.get('MACDh_12_26_9'))
        
        if not np.isnan(macd) and not np.isnan(macd_signal):
            if macd > macd_signal and not np.isnan(macd_hist) and not np.isnan(macd_hist_prev):
                if macd_hist > macd_hist_prev:
                    macd_score = 100  # Bullish and accelerating
                else:
                    macd_score = 75   # Bullish but decelerating
                bullish_count += 1
            elif macd > macd_signal:
                macd_score = 75
                bullish_count += 1
            elif macd < macd_signal and not np.isnan(macd_hist) and not np.isnan(macd_hist_prev):
                if macd_hist < macd_hist_prev:
                    macd_score = -100  # Bearish and accelerating
                else:
                    macd_score = -75   # Bearish but decelerating
                bearish_count += 1
            elif macd < macd_signal:
                macd_score = -75
                bearish_count += 1
            else:
                macd_score = 0
            scores.append(macd_score)
            weights.append(15)
        
        # 3. RSI Momentum - 15%
        rsi = safe_get(latest.get('RSI_14'))
        if not np.isnan(rsi):
            # RSI scoring: 0-30 = oversold (bullish reversal), 70-100 = overbought (bearish reversal)
            if rsi < 30:
                rsi_score = 75   # Oversold - potential buy
                bullish_count += 1
            elif rsi < 40:
                rsi_score = 50
                bullish_count += 1
            elif rsi > 70:
                rsi_score = -75  # Overbought - potential sell
                bearish_count += 1
            elif rsi > 60:
                rsi_score = -50
                bearish_count += 1
            else:
                rsi_score = 0    # Neutral zone
            scores.append(rsi_score)
            weights.append(15)
        
        # 4. ADX Trend Strength - 10%
        adx_col = 'ADX_14'
        if adx_col in df.columns:
            adx = safe_get(latest.get(adx_col))
            if not np.isnan(adx):
                # ADX > 25 indicates strong trend, < 20 indicates weak trend
                # We combine with trend direction for scoring
                trend_direction = scores[0] if scores else 0  # Use trend score
                if adx > 25:
                    # Strong trend - amplify the trend direction
                    adx_score = 75 if trend_direction > 0 else (-75 if trend_direction < 0 else 0)
                elif adx > 20:
                    adx_score = 50 if trend_direction > 0 else (-50 if trend_direction < 0 else 0)
                else:
                    adx_score = 25 if trend_direction > 0 else (-25 if trend_direction < 0 else 0)
                scores.append(adx_score)
                weights.append(10)
        
        # 5. Bollinger %B Position - 10%
        pctb_col = 'BB_PctB_20'
        if pctb_col in df.columns:
            pct_b = safe_get(latest.get(pctb_col))
            if not np.isnan(pct_b):
                # %B > 0.8 = near upper band (potentially overbought)
                # %B < 0.2 = near lower band (potentially oversold)
                if pct_b > 1.0:
                    pctb_score = -75  # Above upper band
                    bearish_count += 1
                elif pct_b > 0.8:
                    pctb_score = -50
                    bearish_count += 1
                elif pct_b < 0.0:
                    pctb_score = 75   # Below lower band
                    bullish_count += 1
                elif pct_b < 0.2:
                    pctb_score = 50
                    bullish_count += 1
                else:
                    pctb_score = 0    # Middle zone
                scores.append(pctb_score)
                weights.append(10)
        
        # 6. Golden/Death Cross - 10%
        cross_col = 'Golden_Cross'
        if cross_col in df.columns:
            # Look for recent crosses (within last 20 days)
            recent_crosses = df[cross_col].tail(20)
            if (recent_crosses == 1).any():
                cross_score = 100  # Recent golden cross
                bullish_count += 1
            elif (recent_crosses == -1).any():
                cross_score = -100  # Recent death cross
                bearish_count += 1
            else:
                # No recent cross, check current position
                if not np.isnan(sma_50) and not np.isnan(sma_200) and sma_50 > sma_200:
                    cross_score = 50  # In golden cross state
                elif not np.isnan(sma_50) and not np.isnan(sma_200):
                    cross_score = -50  # In death cross state
                else:
                    cross_score = 0
            scores.append(cross_score)
            weights.append(10)
        
        # 7. 12M Return - 10%
        close_series = df['Close'].dropna()
        if len(close_series) >= 2:
            current_price = close_series.iloc[-1]
            price_1y = close_series.iloc[-252] if len(close_series) >= 252 else close_series.iloc[0]
            if price_1y > 0:
                ret_12m = ((current_price / price_1y) - 1) * 100
                if ret_12m > 50:
                    ret_score = 100
                    bullish_count += 1
                elif ret_12m > 20:
                    ret_score = 75
                    bullish_count += 1
                elif ret_12m > 0:
                    ret_score = 50
                    bullish_count += 1
                elif ret_12m > -20:
                    ret_score = -50
                    bearish_count += 1
                else:
                    ret_score = -75
                    bearish_count += 1
                scores.append(ret_score)
                weights.append(10)
        
        # 8. Volume vs Average - 5%
        vol = safe_get(latest.get('Volume'))
        vol_series = df['Volume'].dropna() if 'Volume' in df.columns else pd.Series(dtype=float)
        if not np.isnan(vol) and not vol_series.empty:
            vol_avg = vol_series.tail(20).mean()
            if vol_avg > 0:
                vol_ratio = vol / vol_avg
                if vol_ratio > 2.0:
                    vol_score = 75   # Very high volume
                elif vol_ratio > 1.5:
                    vol_score = 50
                elif vol_ratio > 1.0:
                    vol_score = 25
                elif vol_ratio > 0.5:
                    vol_score = -25
                else:
                    vol_score = -50  # Very low volume
                scores.append(vol_score)
                weights.append(5)
        
        # 9. vs 50DMA - 5%
        if not np.isnan(price) and not np.isnan(sma_50) and sma_50 > 0:
            vs_50 = ((price / sma_50) - 1) * 100
            if vs_50 > 10:
                vs50_score = 75
            elif vs_50 > 5:
                vs50_score = 50
            elif vs_50 > 0:
                vs50_score = 25
                bullish_count += 1
            elif vs_50 > -5:
                vs50_score = -25
                bearish_count += 1
            else:
                vs50_score = -50
                bearish_count += 1
            scores.append(vs50_score)
            weights.append(5)
        
        # 10. vs 200DMA - 5%
        if not np.isnan(price) and not np.isnan(sma_200) and sma_200 > 0:
            vs_200 = ((price / sma_200) - 1) * 100
            if vs_200 > 20:
                vs200_score = 75
            elif vs_200 > 10:
                vs200_score = 50
            elif vs_200 > 0:
                vs200_score = 25
                bullish_count += 1
            elif vs_200 > -10:
                vs200_score = -25
                bearish_count += 1
            else:
                vs200_score = -50
                bearish_count += 1
            scores.append(vs200_score)
            weights.append(5)
        
        # 11. Distance from 52W High - 5%
        high_series = df['High'].dropna() if 'High' in df.columns else pd.Series(dtype=float)
        if not high_series.empty and not np.isnan(price):
            high_52w = high_series.tail(252).max() if len(df) >= 252 else high_series.max()
            if not np.isnan(high_52w) and high_52w > 0:
                dist_52wh = ((price / high_52w) - 1) * 100
                if dist_52wh > -5:
                    dist_score = 100
                elif dist_52wh > -10:
                    dist_score = 75
                elif dist_52wh > -20:
                    dist_score = 50
                else:
                    dist_score = 0
                scores.append(dist_score)
                weights.append(5)
        
        # Calculate weighted composite score
        if not scores or not weights:
            return ('Insufficient Data', 0, 'Could not calculate indicators')
        
        total_weight = sum(weights)
        if total_weight == 0:
            return ('Insufficient Data', 0, 'No valid indicators')
        
        composite_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        
        # Determine rating label
        if composite_score >= 70:
            rating = 'Strong Buy'
        elif composite_score >= 40:
            rating = 'Buy'
        elif composite_score >= -40:
            rating = 'Neutral'
        elif composite_score >= -70:
            rating = 'Sell'
        else:
            rating = 'Strong Sell'
        
        # Generate confluence note
        total_signals = bullish_count + bearish_count
        if total_signals == 0:
            confluence = 'Mixed signals - no clear directional bias'
        elif bullish_count > bearish_count * 2:
            confluence = f'Strong bullish confluence ({bullish_count}/{total_signals} signals)'
        elif bearish_count > bullish_count * 2:
            confluence = f'Strong bearish confluence ({bearish_count}/{total_signals} signals)'
        elif bullish_count > bearish_count:
            confluence = f'Moderate bullish tilt ({bullish_count}/{total_signals} signals)'
        elif bearish_count > bullish_count:
            confluence = f'Moderate bearish tilt ({bearish_count}/{total_signals} signals)'
        else:
            confluence = f'Mixed signals ({bullish_count} bullish, {bearish_count} bearish)'
        
        return (rating, round(composite_score, 1), confluence)
        
    except Exception as e:
        # Log error details for debugging (visible in Streamlit Cloud logs)
        import traceback
        error_details = f"Signal calc error: {str(e)}\n{traceback.format_exc()}"
        print(error_details)  # Will appear in Streamlit Cloud logs
        return ('Error', 0, f'Calculation error: {str(e)}')

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

        # Calculate composite rating (Signal)
        signal_rating, signal_score, signal_note = calculate_composite_rating(df)

        # Ensure signal_rating is always a string for consistent display
        signal_rating_str = str(signal_rating) if signal_rating is not None else 'Error'
        
        rows.append({
            'Ticker': symbol,
            'Company': stock_data.get('name', ''),
            'Country': stock_data.get('country', ''),
            'Subsector': stock_data.get('subsector', ''),
            'Last Price': price,
            'Signal': signal_rating_str,
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

    def color_signal(val):
        """Color code Signal column based on composite rating - using dashboard color scheme."""
        if val == 'Strong Buy':
            return 'color: #10B981; font-weight: bold'  # Dashboard green
        elif val == 'Buy':
            return 'color: #10B981'  # Dashboard green
        elif val == 'Neutral':
            return 'color: #F59E0B'  # Dashboard gold
        elif val == 'Sell':
            return 'color: #EF4444'  # Dashboard red
        elif val == 'Strong Sell':
            return 'color: #EF4444; font-weight: bold'  # Dashboard red
        elif val in ('Insufficient Data', 'Error'):
            return 'color: #6B7280; font-style: italic'  # Gray for error/insufficient states
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
                ("text-align", "center"),
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
    if 'Signal' in display_df.columns:
        styled = styled.map(color_signal, subset=['Signal'])
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
    """Render the color-coded legend with detailed scoring explanation."""
    st.markdown("""
    <div class="legend-text">
    <strong>Sorted by twelve month return, descending.</strong><br><br>
    <strong>Signal (Composite of 11 Weighted Indicators):</strong><br>
    <span style="color:#10B981; font-weight:bold">Strong Buy</span> (Score ≥70) •
    <span style="color:#10B981">Buy</span> (Score 40-69) •
    <span style="color:#F59E0B">Neutral</span> (Score -39 to +39) •
    <span style="color:#EF4444">Sell</span> (Score -69 to -40) •
    <span style="color:#EF4444; font-weight:bold">Strong Sell</span> (Score ≤-70)<br>
    <em>Indicator Weights: Trend 20% • MACD 15% • RSI 15% • ADX 10% • Bollinger %B 10% • Golden/Death Cross 10% • 12M Return 10% • Volume 5% • vs 50DMA 5% • vs 200DMA 5% • Dist from 52W High 5%</em><br><br>
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
        st.title("📊 StockLens")
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

                # DEBUG: Verify Signal column exists and has values
                if 'Signal' not in scorecard.columns:
                    st.error("DEBUG: Signal column missing from scorecard!")
                    st.write("Available columns:", list(scorecard.columns))
                else:
                    signal_values = scorecard['Signal'].unique()
                    # st.write(f"DEBUG: Signal values: {signal_values}")  # Uncomment to debug

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
                        "Signal": st.column_config.TextColumn(alignment="center"),

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

# ============================================================
# TEST FUNCTIONS
# ============================================================

def test_indicators():
    """Test the new indicator functions with sample data."""
    print("=" * 60)
    print("TESTING NEW INDICATORS")
    print("=" * 60)
    
    # Create sample OHLCV data (simulating a stock with trend)
    np.random.seed(42)
    n_days = 250
    
    # Generate trending price data
    trend = np.linspace(100, 150, n_days)  # Uptrend
    noise = np.random.normal(0, 2, n_days)
    close = trend + noise
    
    # Generate OHLC from close
    high = close + np.abs(np.random.normal(2, 1, n_days))
    low = close - np.abs(np.random.normal(2, 1, n_days))
    open_price = close + np.random.normal(0, 1, n_days)
    volume = np.random.randint(1000000, 5000000, n_days)
    
    # Create DataFrame
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_days, freq='D')
    df = pd.DataFrame({
        'Open': open_price,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': volume
    }, index=dates)
    
    print(f"\nSample data: {len(df)} days")
    print(f"Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
    
    # Test ADX
    print("\n--- Testing ADX ---")
    adx = calculate_adx(df)
    print(f"ADX calculated: {adx.notna().sum()} valid values")
    print(f"Latest ADX: {adx.iloc[-1]:.2f}")
    print(f"ADX range: {adx.min():.2f} - {adx.max():.2f}")
    
    # Test Bollinger %B
    print("\n--- Testing Bollinger %B ---")
    pct_b = calculate_bollinger_pctb(df)
    print(f"%B calculated: {pct_b.notna().sum()} valid values")
    print(f"Latest %B: {pct_b.iloc[-1]:.4f}")
    print(f"%B range: {pct_b.min():.4f} - {pct_b.max():.4f}")
    
    # Test Golden Cross
    print("\n--- Testing Golden/Death Cross ---")
    cross = calculate_golden_cross(df)
    golden_count = (cross == 1).sum()
    death_count = (cross == -1).sum()
    print(f"Golden crosses detected: {golden_count}")
    print(f"Death crosses detected: {death_count}")
    
    # Test full indicator pipeline
    print("\n--- Testing Full calculate_indicators() ---")
    df_with_indicators = calculate_indicators(df.copy())
    print(f"Columns added: {list(df_with_indicators.columns.difference(df.columns))}")
    
    # Test Composite Rating
    print("\n--- Testing Composite Rating ---")
    rating, score, note = calculate_composite_rating(df_with_indicators)
    print(f"Rating: {rating}")
    print(f"Score: {score}")
    print(f"Note: {note}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
    
    return True


def test_composite_categories():
    """Test that composite rating produces expected signal categories."""
    print("\n" + "=" * 60)
    print("TESTING COMPOSITE RATING CATEGORIES")
    print("=" * 60)
    
    np.random.seed(42)
    
    test_cases = [
        ("Strong Uptrend", lambda n: np.linspace(100, 200, n)),
        ("Strong Downtrend", lambda n: np.linspace(200, 100, n)),
        ("Sideways", lambda n: 100 + np.random.normal(0, 2, n)),
        ("Volatile Uptrend", lambda n: np.linspace(100, 150, n) + np.random.normal(0, 5, n)),
    ]
    
    for name, price_gen in test_cases:
        n_days = 250
        close = price_gen(n_days)
        high = close + np.abs(np.random.normal(2, 1, n_days))
        low = close - np.abs(np.random.normal(2, 1, n_days))
        open_price = close + np.random.normal(0, 1, n_days)
        volume = np.random.randint(1000000, 5000000, n_days)
        
        dates = pd.date_range(end=pd.Timestamp.now(), periods=n_days, freq='D')
        df = pd.DataFrame({
            'Open': open_price,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume
        }, index=dates)
        
        df = calculate_indicators(df)
        rating, score, note = calculate_composite_rating(df)
        
        print(f"\n{name}:")
        print(f"  Rating: {rating}")
        print(f"  Score: {score}")
        print(f"  Note: {note}")
    
    print("\n" + "=" * 60)
    print("CATEGORY TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    # Check if running in test mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_indicators()
        test_composite_categories()
    else:
        main()
