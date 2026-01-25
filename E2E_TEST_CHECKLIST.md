# E2E Testing Checklist - Printable

**Date**: ________________
**Tester**: ________________
**Status**: READY FOR TESTING

---

## PHASE 1: PROJECT SETUP

- [ ] Application starts without errors: `python app.py`
- [ ] Console shows: "SERPER_API_KEY loaded"
- [ ] No errors in `rank_tracker.log`
- [ ] Web UI loads: `http://localhost:5000`
- [ ] Create new project named "E2E Test"
- [ ] Project appears in project list
- [ ] Project persists after app restart
- [ ] Can select project without errors

---

## PHASE 2: CONFIGURATION & DATA ENTRY

### Business Names
- [ ] Add business name: "Test Business"
- [ ] Add alias: "Test Company"
- [ ] Add alias: "TB Services"
- [ ] All names appear in UI
- [ ] Database shows all names:
  ```bash
  python -c "import sqlite3, json; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT business_names FROM projects WHERE name=\"E2E Test\"'); print(json.loads(c.fetchone()[0]))"
  ```
- [ ] Can edit names
- [ ] Can remove names

### Keywords
- [ ] Add keyword 1
- [ ] Add keyword 2
- [ ] Add keyword 3
- [ ] All keywords appear in UI
- [ ] Database shows all keywords:
  ```bash
  python -c "import sqlite3, json; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT keywords FROM projects WHERE name=\"E2E Test\"'); print(json.loads(c.fetchone()[0]))"
  ```

### Website URL
- [ ] Add website: "https://example.com"
- [ ] Website appears in project settings
- [ ] Can update website
- [ ] Website is stored in database

### Polygon Area
- [ ] Open map interface
- [ ] Draw polygon with 4+ points
- [ ] Polygon displays on map
- [ ] Polygon is saved
- [ ] Polygon persists after page reload
- [ ] Database shows polygon coordinates

---

## PHASE 3: SCAN EXECUTION

### Start Scan
- [ ] Configure scan:
  - Grid spacing: 500m
  - Keywords: All 3 keywords
  - Area: Your polygon
- [ ] Click "Run Scan"
- [ ] Scan job created with unique ID
- [ ] No immediate errors
- [ ] Progress bar appears
- [ ] Status shows "Running"
- [ ] Scan appears in scan history

### Grid Calculation
- [ ] Progress advances as points processed
- [ ] `rank_tracker.log` shows grid calculation
- [ ] Check grid point count:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM scan_points WHERE scan_id = (SELECT id FROM scans ORDER BY id DESC LIMIT 1)'); print(f'Grid points: {c.fetchone()[0]}')"
  ```
- [ ] Points > 0 and reasonable for your area
- [ ] Points are within polygon bounds
- [ ] No duplicate points

### API Calls (REAL, NOT DUMMY)
- [ ] Log shows "🔴 Real API Call" messages
- [ ] Log does NOT show "Dummy mode"
- [ ] Log does NOT show "Cache-only"
- [ ] Real business names in results (not "Competitor 1")
- [ ] Results include:
  - [ ] Business name/title
  - [ ] Rating (0-5)
  - [ ] Review count
  - [ ] Position/rank
  - [ ] Address

### Business Matching
- [ ] One of your keywords finds your test business
- [ ] Business name matched correctly
- [ ] Rank shows in results
- [ ] If business not found, status = "not_found" (not error)
- [ ] Database records matched business name

### Progress Reporting
- [ ] Progress bar increases (0% → 100%)
- [ ] ETA displayed
- [ ] Points completed counter increments
- [ ] No frozen progress
- [ ] Scan completes with 100% shown
- [ ] Final status: "Complete"

---

## PHASE 4: DATA PERSISTENCE & CACHING

### Scan Point Storage
- [ ] Query points:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM scan_points'); print(f'Total points: {c.fetchone()[0]}')"
  ```
- [ ] Points > 0
- [ ] Each point has:
  - [ ] scan_id
  - [ ] lat, lon (coordinates)
  - [ ] keyword
  - [ ] rank (if found)
  - [ ] status
  - [ ] timestamp

### Competitor Snapshots Storage
- [ ] Query:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_snapshots'); print(f'Snapshots: {c.fetchone()[0]}')"
  ```
- [ ] Snapshot count > 0
- [ ] Sample competitor:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT competitor_name, rank, review_count, rating_stars FROM competitor_snapshots LIMIT 1'); print(c.fetchone())"
  ```
- [ ] Name is real (not "Competitor 1")
- [ ] Rank is 1-30
- [ ] Review count >= 0 (or NULL)
- [ ] Rating is 0-5 (or NULL)

### **CRITICAL: Competitor History Storage**
**This was the main bug - must have records now!**
- [ ] Query:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_history'); print(f'History records: {c.fetchone()[0]}')"
  ```
- [ ] **History count > 0** ← MUST BE FIXED!
- [ ] If count = 0: **BUG NOT FIXED**
- [ ] Sample history:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT competitor_name, rank, scan_date FROM competitor_history LIMIT 5'); [print(row) for row in c.fetchall()]"
  ```
- [ ] All names are real (not fake)
- [ ] No "Competitor 1", "Competitor 2"
- [ ] Scan dates are current

### Point History Storage
- [ ] Query:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM point_history'); print(f'Point history: {c.fetchone()[0]}')"
  ```
- [ ] Point history count > 0
- [ ] Sample:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT city, keyword, matched_business_name, local_pack_rank FROM point_history LIMIT 1'); print(c.fetchone())"
  ```
- [ ] City is name (not coordinates)
- [ ] Keyword matches what was configured
- [ ] Business name is correct (or NULL if not found)
- [ ] Rank is number or NULL

### Cache Creation
- [ ] Check cache directory:
  ```bash
  ls cache/ | wc -l
  ```
- [ ] Cache file count > 0
- [ ] Files are valid JSON:
  ```bash
  python -c "import json, os; files = [f for f in os.listdir('cache') if f.endswith('.json')]; print(f'Valid cache files: {len(files)}')"
  ```
- [ ] Cache contains search results
- [ ] Cache locations are correct (not Rome/Milano/etc.)

### No Dummy Data in Cache
- [ ] Check for fake competitor names:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_history WHERE competitor_name LIKE \"Competitor %\"'); print(f'Fake competitors: {c.fetchone()[0]}')"
  ```
- [ ] Result = 0 (no fakes)
- [ ] If > 0: **DUMMY MODE ISSUE**

---

## PHASE 5: USER INTERFACE & DATA VISUALIZATION

### Dashboard Display
- [ ] Navigate to Dashboard
- [ ] Scan appears in scan history
- [ ] Scan date/time correct
- [ ] Number of points processed shown correctly
- [ ] Keywords listed
- [ ] Scan status shows "Complete"
- [ ] Competitors found count > 0
- [ ] No error messages

### Map Display
- [ ] Navigate to Map tab
- [ ] Polygon area visible
- [ ] Grid points visible on map
- [ ] Point count matches database
- [ ] Colors represent status (green=success, red=not_found, etc.)
- [ ] Click point shows details popup
- [ ] Details include:
  - [ ] Coordinates
  - [ ] Keyword
  - [ ] Business rank
  - [ ] Competitors list
  - [ ] Status

### Point Details View
- [ ] Click on a map point
- [ ] Details panel/modal opens
- [ ] Shows:
  - [ ] Lat/lon coordinates
  - [ ] Keyword
  - [ ] City/location
  - [ ] Business name (if found)
  - [ ] Local pack rank
  - [ ] Organic rank
  - [ ] Top competitors
  - [ ] Status

### Competitors Tab
- [ ] Navigate to Competitors page
- [ ] Competitor list populated
- [ ] List count > 0
- [ ] Each competitor shows:
  - [ ] Name (real business name)
  - [ ] Times ranked (count)
  - [ ] Dominance score
  - [ ] Average rank
  - [ ] Top rank achieved
- [ ] No "Competitor 1", "Competitor 2", etc.
- [ ] Can sort by name, count, score
- [ ] Can filter by keyword

### Charts & Analytics
- [ ] Dashboard has rank distribution chart
- [ ] Chart displays correctly (bars visible)
- [ ] Y-axis shows frequency
- [ ] X-axis shows ranks (1-30)
- [ ] Competitor dominance chart visible
- [ ] Top competitors highlighted
- [ ] Charts are interactive (hover shows data)

### Rankings Table
- [ ] Rankings/Results table visible
- [ ] Shows all scanned points
- [ ] Columns include:
  - [ ] Point ID / Coordinates
  - [ ] Keyword
  - [ ] City
  - [ ] Business Local Rank
  - [ ] Business Organic Rank
  - [ ] Status
  - [ ] Scan Date
- [ ] Can sort columns
- [ ] Can search/filter keywords
- [ ] Pagination works (if >25 rows)
- [ ] Click row shows point details

---

## PHASE 6: DATA INTEGRITY & ANALYTICS

### Admin Integrity Check
- [ ] Run:
  ```bash
  python admin_cleanup.py --check
  ```
- [ ] Output shows:
  - [ ] projects: 1+ rows
  - [ ] scans: 1+ rows
  - [ ] scan_points: >0 rows
  - [ ] point_history: >0 rows
  - [ ] competitor_snapshots: >0 rows
  - [ ] **competitor_history: >0 rows** ← KEY!
- [ ] No critical warnings

### Verify No Dummy Data
- [ ] Check fake competitors:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_history WHERE competitor_name LIKE \"Competitor %\"'); print(c.fetchone()[0])"
  ```
- [ ] Result = 0
- [ ] All competitors are real business names
- [ ] No "Competitor 1", "Competitor 2"

### Verify Geographic Correctness
- [ ] Check cache locations:
  ```bash
  python -c "import json, os; files = [f for f in os.listdir('cache') if f.endswith('.json')][:5];
  for f in files:
    with open(f'cache/{f}') as fp:
      data = json.load(fp)
      if 'searchParameters' in data:
        print(f'Location: {data[\"searchParameters\"].get(\"location\")}')"
  ```
- [ ] Locations match your polygon area
- [ ] No Rome, Milano, Torino, Naples data
- [ ] No data from wrong geographic regions

### Verify Logging Works
- [ ] Check log file exists:
  ```bash
  ls rank_tracker.log
  ```
- [ ] Log file created
- [ ] Review log contents:
  ```bash
  head -20 rank_tracker.log
  ```
- [ ] Contains timestamps
- [ ] Contains INFO messages
- [ ] Contains API messages
- [ ] Contains completion message
- [ ] Format is structured (YYYY-MM-DD HH:MM:SS)
- [ ] No ERROR messages (unless expected)

### Run Second Complete Scan
- [ ] Create another test keyword
- [ ] Run second scan
- [ ] Second scan has different ID
- [ ] First scan data still intact
- [ ] Database row counts increased appropriately
  ```bash
  python admin_cleanup.py --check
  ```
- [ ] Can view both scans independently

---

## PHASE 7: ERROR HANDLING & EDGE CASES

### Empty Results Handling
- [ ] Search for keyword unlikely to match your business
- [ ] Scan completes without crashing
- [ ] Point status shows "not_found"
- [ ] No errors in logs
- [ ] Competitor list empty (not errored)
- [ ] Database records "not found" state

### API Error Handling (Optional)
- [ ] Temporarily disable API key in .env
- [ ] Run small scan
- [ ] Points marked as "error"
- [ ] Log shows error message
- [ ] Scan doesn't crash
- [ ] Error is helpful/descriptive
- [ ] Restore API key after test

### Data Consistency
- [ ] No orphaned competitor records
- [ ] All scan_points link to scans
- [ ] All competitors link to points
- [ ] Foreign key relationships maintained
- [ ] Required fields always populated

---

## FINAL AUTOMATED TESTS

Run automated test suite:
```bash
python test_e2e_automated.py
```

- [ ] Database test passed
- [ ] Tables test passed
- [ ] Data population test passed
- [ ] No dummy data test passed
- [ ] Geographic correctness test passed
- [ ] Logging test passed
- [ ] Competitor fields test passed
- [ ] Point completeness test passed
- [ ] Data correlation test passed
- [ ] Data consistency test passed
- [ ] **All automated tests PASSED**

---

## SIGN-OFF

### Critical Success Indicators

Must all be TRUE:

- [ ] **competitor_history has records** (was empty - BUG FIX)
- [ ] **No "Competitor 1" fake data** (was polluting data)
- [ ] **All competitor data from correct locations** (cache was poisoned)
- [ ] **rank_tracker.log exists with no errors** (logging was added)
- [ ] **All tables display correct data** (UI validation)
- [ ] **Database integrity check passes** (data validation)

### Pass/Fail

**If all checkboxes are checked**: ✅ **PASS** - System is ready for production

**If any critical indicator is FALSE**: ❌ **FAIL** - Issues remain

---

**Tested By**: ________________
**Date**: ________________
**Result**: [ ] PASS  [ ] FAIL
**Notes**: _______________________________________________
_______________________________________________________

---

## QUICK HELP

### If competitor_history is still 0:
1. Check `rank_tracker.log` for insert errors
2. Verify .env has `USE_DUMMY_MODE=false`
3. Check API key is valid (40 characters)
4. Run: `python admin_cleanup.py --check`

### If seeing "Competitor 1", "Competitor 2":
1. Verify `USE_DUMMY_MODE=false` in .env
2. Restart app
3. Create NEW project (don't reuse old)
4. Run fresh scan

### If locations are wrong (Rome/Milano):
1. This was already fixed - cache was cleared
2. If persists, run: `rm -r cache/ && mkdir cache/`
3. Restart app and run fresh scan

### If no log file:
1. It will be created on app start
2. Check permissions on directory
3. Monitor with: `tail -f rank_tracker.log`

