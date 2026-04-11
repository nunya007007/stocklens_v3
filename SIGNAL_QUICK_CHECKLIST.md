# Signal Column Audit - Quick Action Checklist for Mark

## 🔴 IMMEDIATE ACTIONS (Do These First)

### 1. Check Streamlit Cloud Dashboard (5 minutes)
- [ ] Go to https://share.streamlit.io/
- [ ] Find StockLens V3 app
- [ ] Verify these settings:
  - **Repository:** `nunya007007/stocklens_v3` 
  - **Branch:** `main`
  - **Main file:** `app.py`
- [ ] Check "Last deployed" timestamp - should be recent

### 2. Check Deployment Logs (5 minutes)
- [ ] In Streamlit Cloud, click "Logs" or "Manage app" → "Logs"
- [ ] Search for errors containing:
  - `Signal`
  - `calculate_composite_rating`
  - `KeyError`
  - `ModuleNotFoundError`
- [ ] Screenshot any errors found

### 3. Verify GitHub Has Latest Code (2 minutes)
- [ ] Go to https://github.com/nunya007007/stocklens_v3/commits/main/
- [ ] Confirm top commit is: `84ba51d fix: Signal column runtime issues on Streamlit Cloud`
- [ ] If not, code hasn't been pushed properly

---

## 🟡 SECONDARY CHECKS (If Immediate Actions Don't Reveal Issue)

### 4. Force App Rebuild
- [ ] In Streamlit Cloud app settings, click "Reboot" or "Restart"
- [ ] Wait for rebuild (2-3 minutes)
- [ ] Refresh app and check if Signal appears

### 5. Clear All Caches
- [ ] Browser: Hard refresh with `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
- [ ] Try incognito/private browsing mode
- [ ] Streamlit Cloud: Click "Clear cache" in app settings

### 6. Test Local vs Cloud
- [ ] Run locally: `cd /Users/mark/.openclaw/workspace/stocklens_v3 && streamlit run app.py`
- [ ] Verify Signal column appears locally
- [ ] Compare: If local works but cloud doesn't = deployment issue

---

## 🟢 REPORT BACK

After completing checks above, report:
1. Streamlit Cloud settings (repo, branch, last deployed time)
2. Any errors found in logs
3. Whether Signal column appears locally
4. Whether app has been rebuilt recently

---

## Common Issues & Quick Fixes

| Symptom | Likely Cause | Quick Fix |
|---------|--------------|-----------|
| Old deployment timestamp | App not rebuilt | Click "Reboot" in settings |
| Wrong repo/branch | Misconfigured deployment | Update settings to `nunya007007/stocklens_v3` + `master` |
| `KeyError: 'Signal'` in logs | Code mismatch | Verify commit `84ba51d` is on GitHub |
| Works locally, not cloud | Environment difference | Add debug logging, check yfinance data |
| Column missing entirely | Column config issue | Temporarily remove `column_config` for Signal |

---

## Debug Commands (Run in Terminal)

```bash
# Check local git status
cd /Users/mark/.openclaw/workspace/stocklens_v3
git status
git log --oneline -3

# Verify GitHub has latest
git fetch origin
git log origin/master --oneline -3

# Check for uncommitted changes
git diff

# Push if needed
git push origin master
```

---

## Need Help?

If stuck on any step, share:
1. Screenshot of Streamlit Cloud settings
2. Copy of deployment logs (last 50 lines)
3. Output of `git log --oneline -5` from local repo
