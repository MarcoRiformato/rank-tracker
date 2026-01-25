# Run Real Business Test - Quick Start

**Status**: Setup complete, ready to execute
**Project ID**: 4
**Business**: Edil Italia di Sergio Fuscaldo
**Keywords**: ristrutturazioni saronno, ristrutturazione bagno, ristrutturazione tetto
**Coverage**: 25km radius around Saronno with 5km grid spacing
**Grid Points**: 74 locations to scan
**Expected Duration**: 25-37 minutes (first run, includes API calls)

---

## Option A: Run Via Web UI (Recommended)

1. Open web UI in browser
2. Select Project: **4 - Real Business Test - Edil Italia**
3. Click "New Scan"
4. Check the 3 keywords:
   - ristrutturazioni saronno
   - ristrutturazione bagno
   - ristrutturazione tetto
5. Grid configuration (pre-filled):
   - Radius: 25km
   - Spacing: 5km
6. Click "Start Scan"
7. Monitor progress in dashboard

---

## Option B: Run Via API Call

```bash
curl -X POST http://localhost:5000/api/check-rankings \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 4,
    "keywords": ["ristrutturazioni saronno", "ristrutturazione bagno", "ristrutturazione tetto"],
    "polygon": null,
    "grid_spacing": 5,
    "service_center": [45.3156, 8.8563],
    "radius": 25
  }'
```

---

## Monitor Execution

```bash
# Watch logs in real-time
tail -f rank_tracker.log
```

Look for:
- API calls and cache hits
- Competitors being extracted
- "Skipped duplicate competitor" messages (deduplication working)

---

## After Scan Completes

### 1. Check System Health
```bash
python3 verify_system.py
```

Shows:
- ✓ Database integrity
- ✓ Data field population
- ✓ Number of records with ratings/reviews

### 2. View Results in Dashboard
- Total points scanned: 222 (74 points × 3 keywords)
- Your business rankings at each location
- Competitors discovered
- Heatmap visualization

### 3. Query Results in Python
```python
import sqlite3
conn = sqlite3.connect('scans.db')
c = conn.cursor()

# Total competitors found
c.execute("SELECT COUNT(*) FROM competitor_history WHERE project_id = 4")
print(f"Competitors found: {c.fetchone()[0]}")

# How many with ratings (should be high)
c.execute("""
  SELECT COUNT(*) FROM competitor_history
  WHERE project_id = 4 AND rating_stars IS NOT NULL
""")
print(f"With ratings: {c.fetchone()[0]}")

# How many with addresses
c.execute("""
  SELECT COUNT(*) FROM competitor_history
  WHERE project_id = 4 AND address IS NOT NULL AND address != ''
""")
print(f"With addresses: {c.fetchone()[0]}")

# Your business - how many points did we find you?
c.execute("""
  SELECT COUNT(*) FROM scan_points
  WHERE matched_business_name IS NOT NULL
""")
print(f"Locations where you were found: {c.fetchone()[0]}")
```

---

## What To Expect

### If Successful ✅
```
Your Business Rankings:
  - Found in multiple locations
  - local_pack_rank: 1-10 ideally (top 10 on maps)
  - organic_rank: 1-50 (visible in search)
  - display_rank: Shows on heatmap

Competitors:
  - 5-15 per location
  - Names deduplicated (no "Cla.Vi." duplicates)
  - Rich data: ratings, reviews, addresses, phones
  - Properly organized by location

Data Quality:
  - 95%+ with addresses
  - 80%+ with ratings
  - 70%+ with review counts
  - 60%+ with phone numbers
```

### If Issues ✗
See **SYSTEM_REFERENCE.md** troubleshooting section

---

## Important Notes

### API Calls
- 74 grid points × 3 keywords = 222 API calls
- Caching: First run ~7 seconds per call average
- Subsequent runs much faster (cached)

### Data Fields Populated
With the ratingCount fix applied:
- ✅ competitor_name
- ✅ rank (position on maps)
- ✅ rating_stars (4.5, 3.8, etc.)
- ✅ review_count (243, 89, etc.) ← NOW WORKING
- ✅ address
- ✅ phone_number
- ✅ website
- ✅ category

### Three Ranking Types Saved
- **local_pack_rank**: Your position on Google Maps (1-3 most visible)
- **organic_rank**: Your position in search results
- **display_rank**: Shown on heatmap (= local_pack_rank)

---

## Reference Files

- **SYSTEM_REFERENCE.md** - Complete system documentation & troubleshooting
- **verify_system.py** - Diagnostic tool for checking system health
- **rank_tracker.log** - Execution logs

---

**Ready to start? Choose Option A (Web UI) or Option B (API) above.**
