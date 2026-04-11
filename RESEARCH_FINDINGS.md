# Streamlit Column Headers & Title Styling Research Findings

## Executive Summary

The core issue is that **Streamlit's `st.dataframe` does NOT fully support Pandas Styler's `set_table_styles()` for header styling**. This is a known limitation with multiple GitHub issues open since 2022-2023. The current CSS injection approach in StockLens V3 has incorrect selectors for the modern Streamlit dataframe component.

---

## Problem Analysis

### 1. Current CSS Selectors (NOT WORKING)

The current code in `app.py` uses:

```css
div[data-testid="stDataFrame"] thead tr th {
    background-color: var(--bg-secondary) !important;
    color: #14B8A6 !important;
    text-align: center !important;
    border-bottom: 1px solid var(--border-primary) !important;
}
```

**Why it fails:**
- `st.dataframe` in modern Streamlit uses a **React-based grid component** (Glide Data Grid), not a standard HTML table
- The `data-testid="stDataFrame"` selector targets the container, but the internal grid doesn't use standard `<thead>` or `<th>` elements
- CSS cannot penetrate the Shadow DOM or React component boundaries

### 2. Root Cause

From GitHub Issue #6958 and #7260:
- `st.dataframe` uses a custom grid renderer that ignores most CSS table styling
- Pandas Styler's `set_table_styles()` with `selector: 'th'` does NOT work with `st.dataframe`
- The styling works with `st.table()` but that component lacks interactivity (sorting, resizing)

---

## Working Solutions

### SOLUTION 1: Use `st.table()` with Pandas Styler (RECOMMENDED for full styling control)

**Trade-off:** Loses interactive features (sorting, column resizing) but gains full styling control.

```python
import streamlit as st
import pandas as pd

# Your dataframe
df = pd.DataFrame(...)

# Define styles
styles = [
    {
        "selector": "th",
        "props": [
            ("background-color", "#141720"),  # Dark background
            ("color", "#14B8A6"),              # Teal text
            ("text-align", "center"),
            ("font-weight", "bold"),
            ("border-bottom", "1px solid rgba(180, 188, 208, 0.15)"),
        ]
    },
    {
        "selector": "td",
        "props": [
            ("background-color", "#1E2238"),
            ("color", "#B4BCD0"),
            ("text-align", "center"),
            ("border-bottom", "1px solid rgba(180, 188, 208, 0.08)"),
        ]
    }
]

# Apply styling
styled_df = df.style.set_table_styles(styles)

# Display with st.table (NOT st.dataframe)
st.table(styled_df)
```

### SOLUTION 2: Theme Configuration via `.streamlit/config.toml`

**Best for:** Global theme consistency, limited customization options.

Create `/stocklens_v3/.streamlit/config.toml`:

```toml
[theme]
base = "dark"
primaryColor = "#F59E0B"  # Gold for accents
backgroundColor = "#0A0B0F"
secondaryBackgroundColor = "#141720"
textColor = "#FFFFFF"

# Dataframe-specific theming (Streamlit 1.28+)
dataframeHeaderBackgroundColor = "#141720"
dataframeBorderColor = "#374151"
```

**Limitations:**
- `dataframeHeaderBackgroundColor` only controls background, not text color
- Cannot set header text color to teal via config.toml
- Limited to single color for all dataframe headers

### SOLUTION 3: CSS Injection with Correct Selectors (PARTIAL - for titles only)

**Works for:** `st.title`, `st.header`, `st.subheader` styling

```python
st.markdown("""
<style>
    /* Title styling - WORKS */
    h1 {
        color: #F59E0B !important;  /* Gold */
    }
    
    /* Header styling - WORKS */
    h2 {
        color: #F59E0B !important;  /* Gold */
    }
    
    h3 {
        color: #F59E0B !important;  /* Gold */
    }
    
    /* Alternative: Target Streamlit's specific classes */
    .stHeading h1 {
        color: #F59E0B !important;
    }
    
    /* For st.markdown with HTML */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #F59E0B !important;
    }
</style>
""", unsafe_allow_html=True)
```

### SOLUTION 4: Hybrid Approach (RECOMMENDED for StockLens V3)

**Combines:** Config.toml for dataframe headers + CSS for titles + Pandas Styler for cell colors

**Step 1:** Create `.streamlit/config.toml`:
```toml
[theme]
base = "dark"
primaryColor = "#F59E0B"
backgroundColor = "#0A0B0F"
secondaryBackgroundColor = "#141720"
textColor = "#FFFFFF"
dataframeHeaderBackgroundColor = "#141720"
dataframeBorderColor = "#374151"
```

**Step 2:** Use Pandas Styler for cell-level colors (this WORKS with st.dataframe):
```python
def style_scorecard(df):
    display_df = df.drop(columns=['_symbol'], errors='ignore').copy()
    
    # Coerce numeric columns
    numeric_cols = ['12M Ret', 'RSI(14)', 'vs 50DMA', 'vs 200DMA', 'Dist 52WH']
    for c in numeric_cols:
        if c in display_df.columns:
            display_df[c] = pd.to_numeric(display_df[c], errors='coerce')

    def color_signal(val):
        if val == 'Strong Buy': return 'color: #10B981; font-weight: bold'
        elif val == 'Buy': return 'color: #10B981'
        elif val == 'Neutral': return 'color: #F59E0B'
        elif val == 'Sell': return 'color: #EF4444'
        elif val == 'Strong Sell': return 'color: #EF4444; font-weight: bold'
        return 'color: #6B7280; font-style: italic'

    styled = display_df.style
    
    # Apply cell-level colors (THIS WORKS with st.dataframe)
    if 'Signal' in display_df.columns:
        styled = styled.map(color_signal, subset=['Signal'])
    
    # Format numbers
    styled = styled.format({
        '12M Ret': '{:+.2f}%',
        'RSI(14)': '{:.1f}',
        'vs 50DMA': '{:+.2f}%',
        'vs 200DMA': '{:+.2f}%',
        'Dist 52WH': '{:.2f}%',
    }, na_rep='—')
    
    return styled
```

**Step 3:** CSS for titles:
```python
st.markdown("""
<style>
    h1, h2, h3 {
        color: #F59E0B !important;
    }
</style>
""", unsafe_allow_html=True)
```

**Step 4:** Display with `st.dataframe`:
```python
styled = style_scorecard(scorecard)
st.dataframe(
    styled,
    use_container_width=True,
    height=table_height,
    hide_index=True,
    column_config={...}
)
```

---

## Specific Solutions for StockLens V3 Requirements

### 1. Centering Dataframe Column Headers

**Option A:** Via config.toml (limited control):
```toml
[theme]
dataframeHeaderBackgroundColor = "#141720"
```

**Option B:** Use `st.table()` with full CSS control (recommended if sorting not critical):
```python
styles = [{
    "selector": "th",
    "props": [("text-align", "center")]
}]
st.table(df.style.set_table_styles(styles))
```

**Option C:** Use `column_config` in `st.dataframe()` (alignment only, not header color):
```python
st.dataframe(
    df,
    column_config={
        "Ticker": st.column_config.TextColumn(alignment="center"),
        "Signal": st.column_config.TextColumn(alignment="center"),
    }
)
```

### 2. Changing Column Header Colors to Teal

**Unfortunately:** Streamlit does NOT support custom header text colors via `st.dataframe`.

**Workarounds:**
1. **Use `st.table()`** - Full styling control but no interactivity
2. **Use `config.toml`** - Can only set header background, not text color
3. **Use HTML table** via `st.markdown()` - Full control but manual implementation

### 3. Changing st.title/st.header Colors to Gold

**Working CSS:**
```python
st.markdown("""
<style>
    /* Primary method */
    h1, h2, h3 {
        color: #F59E0B !important;
    }
    
    /* Backup selectors */
    .stHeading h1, .stHeading h2, .stHeading h3 {
        color: #F59E0B !important;
    }
    
    /* For markdown-generated headers */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #F59E0B !important;
    }
</style>
""", unsafe_allow_html=True)
```

**Alternative:** Use HTML directly in markdown:
```python
st.markdown('<h1 style="color:#F59E0B;">📊 StockLens</h1>', unsafe_allow_html=True)
st.markdown('<h2 style="color:#F59E0B;">Index-Level Dashboard</h2>', unsafe_allow_html=True)
```

---

## Implementation Recommendations for StockLens V3

### Immediate Fix (Minimal Changes)

1. **Create `.streamlit/config.toml`** with theme settings
2. **Update CSS** in app.py to use simpler selectors for titles
3. **Keep using `st.dataframe`** with Pandas Styler for cell colors
4. **Accept limitation:** Header text color will be default (white), background can be themed

### Enhanced Fix (Better Styling)

1. **Switch to `st.table()`** for the scorecard view to get full header styling control
2. **Keep `st.dataframe`** for views where interactivity is critical
3. **Use HTML markdown** for all titles to ensure gold color

### Code Changes Required

**File: `.streamlit/config.toml`** (NEW)
```toml
[theme]
base = "dark"
primaryColor = "#F59E0B"
backgroundColor = "#0A0B0F"
secondaryBackgroundColor = "#141720"
textColor = "#FFFFFF"
dataframeHeaderBackgroundColor = "#141720"
dataframeBorderColor = "#374151"
```

**File: `app.py` - Simplified CSS**
```python
st.markdown("""
<style>
    /* App background */
    .stApp {
        background: linear-gradient(135deg, #0A0B0F 0%, #141720 50%, #1E2238 100%);
    }
    
    /* Title colors - Gold */
    h1, h2, h3 {
        color: #F59E0B !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #141720;
        color: #B4BCD0;
        border: 1px solid #374151;
        border-radius: 8px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #8B5CF6;
        color: #FFFFFF;
    }
    
    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #252A3F;
        border: 1px solid #374151;
        border-radius: 10px;
    }
    
    /* Hide branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)
```

---

## References

1. **GitHub Issue #6958:** "Keep header style when using st.dataframe" (Open since July 2023)
2. **GitHub Issue #7260:** "Pandas Styler not working with set_table_styles" (Open since Aug 2023)
3. **GitHub Issue #4830:** "st.dataframe doesn't accept formatting as it used to" (Open since June 2022)
4. **Streamlit Docs:** [Theming - Customize colors and borders](https://docs.streamlit.io/develop/concepts/configuration/theming-customize-colors-and-borders)
5. **Streamlit Docs:** [config.toml reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)

---

## Summary Table

| Requirement | Solution | Status |
|-------------|----------|--------|
| Center dataframe headers | `st.table()` + CSS or `column_config` alignment | ✅ Works |
| Header background color teal | `config.toml` `dataframeHeaderBackgroundColor` | ✅ Works |
| Header text color teal | NOT possible with `st.dataframe` | ❌ Limitation |
| Title color gold | CSS `h1, h2, h3` selectors | ✅ Works |
| Cell-level colors | Pandas Styler `.map()` | ✅ Works |
| Full header styling control | Use `st.table()` instead | ✅ Alternative |
