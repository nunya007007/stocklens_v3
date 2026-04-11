# StockLens V3 Signal Column Deployment Audit Plan

## Executive Summary
The Signal column (composite rating) works locally but fails to display on Streamlit Cloud deployment. This audit plan provides a systematic approach to identify and resolve the root cause across the entire deployment pipeline.

**Current Status:**
- ✅ Local testing: Signal column works
- ✅ GitHub commits: Pushed to `nunya007007/stocklens_v3` 
- ❌ Streamlit Cloud: Signal column NOT visible
- 🔍 Last commit: `84ba51d` - "fix: Signal column runtime issues on Streamlit Cloud"

---

## PHASE 1: Streamlit Cloud Configuration Verification

### Step 1.1: Access Streamlit Cloud Dashboard

**Instructions for Mark:**

1. Go to <https://share.streamlit.io/> and sign in
2. Navigate to your apps dashboard
3. Find the StockLens V3 app
4. Click on the app to open its management page

### Step 1.2: Verify Repository and Branch Settings

**Check these settings in the Streamlit Cloud dashboard:**

| Setting | Expected Value | What to Look For |
|---------|---------------|------------------|
| **Repository** | `nunya007007/stocklens_v3` | Verify it's NOT pointing to a different repo |
| **Branch** | `main` | Confirm it's deploying from `main`, not `master` or another branch |
| **Main file path** | `app.py` | Should point to the correct entry point |
| **Python version** | 3.9+ | Check if there's a version constraint |

**⚠️ CRITICAL:** Take a screenshot of these settings and verify they match.

### Step 1.3: Check Deployment Logs for Errors

**Steps:**
1. In the Streamlit Cloud app management page, click **"Logs"** or **"Manage app"** → **"Logs"**
2. Look for the most recent deployment (should be after commit `84ba51d`)
3. Search for these error patterns:
   - `Signal` (case insensitive)
   - `calculate_composite_rating`
   - `KeyError`
   - `AttributeError`
   - `ModuleNotFoundError`
   - `ImportError`
   - `TypeError`
   - Any Python traceback

**Common errors to look for:**
```
# Missing column errors
KeyError: 'Signal'
KeyError: 'RSI_14'

# Function errors
AttributeError: 'DataFrame' object has no attribute '...'
TypeError: 'NoneType' object is not subscriptable

# Import errors
ModuleNotFoundError: No module named '...'
```

### Step 1.4: Verify App is Actually Rebuilt

**Check the deployment timestamp:**
1. In Streamlit Cloud dashboard, look at **"Last deployed"** timestamp
2. Verify it shows a time AFTER the last commit (`84ba51d`)
3. If timestamp is old, the app hasn't been rebuilt with latest code

**Force a rebuild if needed:**
1. Go to app settings
2. Click **"Reboot"** or **"Restart"**
3. Wait for rebuild to complete
4. Check logs again

### Step 1.5: Check Authentication Settings

**Verify the app is publicly accessible:**
1. In Streamlit Cloud dashboard, check **"App visibility"**
2. Ensure it's set to **"Public"** (not Private)
3. If Private, the app may require login to view

---

## PHASE 2: GitHub Verification

### Step 2.1: Verify Correct Repository

**Check for multiple repos:**
```bash
# Run these commands locally
cd /Users/mark/.openclaw/workspace/stocklens_v3
git remote -v
```

**Expected output:**
```
origin  https://github.com/nunya007007/stocklens_v3.git (fetch)
origin  https://github.com/nunya007007/stocklens_v3.git (push)
```

**Also check GitHub web interface:**
1. Go to <https://github.com/nunya007007/stocklens_v3>
2. Verify the repository exists and is accessible
3. Check if there are multiple repos with similar names:
   - `stocklens_v3`
   - `stocklens-v3`
   - `stocklens_v2`
   - Any forks

### Step 2.2: Verify Commits Are on GitHub

**Check the commit hash matches:**

Local:
```bash
cd /Users/mark/.openclaw/workspace/stocklens_v3
git log --oneline -3
```

GitHub Web:
1. Go to <https://github.com/nunya007007/stocklens_v3/commits/main/>
2. Verify the top commit matches local:
   - Hash: `84ba51d`
   - Message: "fix: Signal column runtime issues on Streamlit Cloud"

### Step 2.3: Verify File Contents on GitHub

**Check the actual file content:**
1. Go to <https://github.com/nunya007007/stocklens_v3/blob/master/app.py>
2. Search for `calculate_composite_rating` - should exist
3. Search for `Signal` column definition - should exist in `build_scorecard`
4. Verify the file is NOT truncated or corrupted

**Quick check - Signal column should appear in these locations:**
- Line ~750-800: `calculate_composite_rating` function definition
- Line ~950-1000: `build_scorecard` function with `'Signal': signal_rating_str`
- Line ~1100-1150: `style_scorecard` with `color_signal` function
- Line ~1250-1300: `st.dataframe` column_config with `"Signal": st.column_config.TextColumn`

---

## PHASE 3: Code Verification

### Step 3.1: Test Signal Column Locally

**Run the app locally:**
```bash
cd /Users/mark/.openclaw/workspace/stocklens_v3
streamlit run app.py
```

**Verify:**
1. App loads without errors
2. Navigate to any theme tab (e.g., "Semiconductors")
3. Check if "Signal" column appears in the table
4. Check if Signal values are populated (Buy, Sell, Neutral, etc.)

### Step 3.2: Compare Local vs GitHub Code

**Generate diff to verify they're identical:**
```bash
cd /Users/mark/.openclaw/workspace/stocklens_v3
git fetch origin
git diff HEAD origin/master
```

**Expected:** No output (means they're identical)

**If there are differences:**
```bash
# Push local changes
git push origin master
```

### Step 3.3: Check for Conditional Logic Hiding the Column

**Search for potential issues:**

```bash
# Check if Signal column is conditionally added
grep -n "if.*Signal" app.py

# Check for any feature flags
grep -n "feature\|enable.*signal\|show.*signal" app.py

# Check for environment-specific code
grep -n "os.environ\|st.secrets\|platform" app.py
```

**Known code paths that could hide Signal:**

1. **Data length check in `calculate_composite_rating`:**
   ```python
   if len(df) < 50:  # Reduced from 200
       return ('Insufficient Data', 0, f'Need at least 50 days of data (have {len(df)})')
   ```
   - If yfinance returns less than 50 days on Cloud, Signal = "Insufficient Data"

2. **Exception handling:**
   ```python
   except Exception as e:
       return ('Error', 0, f'Calculation error: {str(e)}')
   ```
   - Any error returns "Error" as Signal value

3. **Column configuration:**
   ```python
   "Signal": st.column_config.TextColumn(alignment="center"),
   ```
   - If this line is missing or malformed, column may not display

### Step 3.4: Verify DataFrame Construction

**Add debug output temporarily:**

Insert this code before `st.dataframe()` call (around line 1250):

```python
# DEBUG: Verify Signal column
st.write("DEBUG: Scorecard columns:", list(scorecard.columns))
st.write("DEBUG: Signal values:", scorecard['Signal'].unique() if 'Signal' in scorecard.columns else "MISSING")
st.write("DEBUG: Scorecard shape:", scorecard.shape)
```

**Commit and push:**
```bash
git add app.py
git commit -m "DEBUG: Add Signal column diagnostics"
git push origin master
```

**Check Streamlit Cloud logs** for the debug output.

---

## PHASE 4: Alternative Deployment Issues

### Step 4.1: Check for Cache Issues

**Streamlit Cloud cache problems:**

1. **Browser cache:**
   - Hard refresh: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
   - Try incognito/private browsing mode
   - Try different browser

2. **Streamlit Cloud cache:**
   - In app settings, click **"Clear cache"**
   - Or add `?nocache=1` to the URL

3. **GitHub cache:**
   - Streamlit Cloud may cache the GitHub repo
   - Force refresh by making a trivial commit:
     ```bash
     echo "# Deployment bump $(date)" >> README.md
     git add README.md
     git commit -m "Force rebuild"
     git push
     ```

### Step 4.2: Check for Wrong Branch Deployment

**Common issue:** Streamlit Cloud deploying from wrong branch

**Verify branch:**
```bash
# List all branches
cd /Users/mark/.openclaw/workspace/stocklens_v3
git branch -a
```

**If `main` and `master` both exist:**
1. Check Streamlit Cloud settings for which branch is selected
2. Verify Signal code exists on THAT branch:
   ```bash
   git log master --oneline -3
   ```

### Step 4.3: Check for Failed Rebuilds

**Signs of failed rebuild:**
1. Old timestamp on "Last deployed"
2. App behavior doesn't match latest commit
3. Logs show old commit hash

**Force complete rebuild:**
1. Go to Streamlit Cloud → App Settings
2. Click **"Delete"** (this only deletes the deployment, not the repo)
3. Re-deploy from GitHub:
   - Click **"New app"**
   - Select `nunya007007/stocklens_v3`
   - Branch: `main`
   - Main file: `app.py`
   - Deploy

### Step 4.4: Check Python Version Compatibility

**Streamlit Cloud Python version issues:**

1. Check `requirements.txt` exists and has all dependencies:
   ```
   streamlit
   yfinance
   pandas
   plotly
   numpy
   ```

2. Check for Python version-specific code:
   ```bash
   grep -n "3\.14\|3\.13\|3\.12" app.py
   ```

3. If using Python 3.14+ features, ensure Streamlit Cloud supports it

### Step 4.5: Check for Environment Differences

**Local vs Cloud environment differences:**

| Factor | Local | Streamlit Cloud |
|--------|-------|-----------------|
| yfinance data | May have cached data | Fresh fetch every time |
| Network | Your ISP | Cloud provider |
| Timezone | America/Chicago | UTC |
| Python packages | Your versions | Latest from requirements.txt |

**Test with fresh data locally:**
```bash
# Clear local cache
cd /Users/mark/.openclaw/workspace/stocklens_v3
rm -rf ~/.cache/py-yfinance
streamlit run app.py
```

---

## PHASE 5: Diagnostic Checklist

### Quick Verification Steps

Mark should complete this checklist:

#### Streamlit Cloud Settings
- [ ] Repository is `nunya007007/stocklens_v3`
- [ ] Branch is `main`
- [ ] Main file is `app.py`
- [ ] App is set to Public
- [ ] Last deployed timestamp is after commit `84ba51d`

#### GitHub Verification
- [ ] Commit `84ba51d` appears on GitHub
- [ ] File `app.py` contains `calculate_composite_rating` function
- [ ] File `app.py` contains `Signal` column in `build_scorecard`

#### Local Testing
- [ ] Signal column appears when running locally
- [ ] No JavaScript errors in browser console (F12 → Console)

#### Streamlit Cloud Logs
- [ ] Checked logs for errors
- [ ] No `KeyError: 'Signal'`
- [ ] No `ModuleNotFoundError`
- [ ] No Python tracebacks

#### Cache/Browser
- [ ] Hard refreshed browser
- [ ] Tried incognito mode
- [ ] Cleared Streamlit Cloud cache

---

## PHASE 6: Potential Fixes Based on Findings

### Scenario A: Streamlit Cloud Using Wrong Repo/Branch
**Fix:** Update deployment settings to correct repo/branch

### Scenario B: Code Not Actually Deployed
**Fix:** Force rebuild or delete and re-deploy

### Scenario C: yfinance Data Different on Cloud
**Fix:** Lower minimum data requirement further (change 50 to 20 days)

### Scenario D: JavaScript/Browser Issue
**Fix:** Test in different browser, check console errors

### Scenario E: Column Configuration Issue
**Fix:** Remove `column_config` for Signal temporarily to test

### Scenario F: Silent Exception
**Fix:** Add more detailed error logging to `calculate_composite_rating`

---

## Appendix: Debug Code to Add

### A.1: Detailed Signal Debugging

Add this to `calculate_composite_rating` function:

```python
def calculate_composite_rating(df):
    """Calculate composite rating with debug logging."""
    import traceback
    
    try:
        # Log entry
        print(f"DEBUG: calculate_composite_rating called with df.shape={df.shape}")
        
        if len(df) < 50:
            msg = f'Need at least 50 days of data (have {len(df)})'
            print(f"DEBUG: {msg}")
            return ('Insufficient Data', 0, msg)
        
        # ... rest of function ...
        
    except Exception as e:
        error_msg = f"Signal calc error: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        return ('Error', 0, error_msg)
```

### A.2: DataFrame Inspection

Add this before `st.dataframe()`:

```python
# Inspect scorecard before display
print("DEBUG SCORECARD:")
print(f"  Columns: {list(scorecard.columns)}")
print(f"  Shape: {scorecard.shape}")
print(f"  Signal dtype: {scorecard['Signal'].dtype if 'Signal' in scorecard.columns else 'MISSING'}")
print(f"  Signal sample: {scorecard['Signal'].head().tolist() if 'Signal' in scorecard.columns else 'N/A'}")
```

---

## Next Steps

1. **Mark completes Phase 1-2 verification** and reports findings
2. **Based on findings**, implement specific fixes from Phase 6
3. **Re-test** after each fix
4. **Document** what worked for future reference

---

*Audit Plan Created: April 11, 2026*
*Target: Resolve Signal column visibility on Streamlit Cloud*
 column visibility on Streamlit Cloud*
