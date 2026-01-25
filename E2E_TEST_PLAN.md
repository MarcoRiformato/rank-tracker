# End-to-End Test Plan - Rank Tracker

**Purpose**: Validate the complete user journey from project creation to data reporting
**Status**: Ready to execute
**Date**: 2026-01-24

---

## TEST PHASES

### Phase 1: Project Setup
### Phase 2: Configuration & Data Entry
### Phase 3: Scan Execution & API Integration
### Phase 4: Data Persistence & Caching
### Phase 5: UI/Data Visualization
### Phase 6: Data Integrity & Analytics

---

## PHASE 1: PROJECT SETUP

### Test 1.1: Create New Project
**Goal**: Verify project creation and initialization

**Steps**:
1. Open application: `http://localhost:5000`
2. Click "New Project" or equivalent
3. Enter project name: "E2E Test Project"
4. Submit form

**Verify**:
- [ ] Project appears in project list
- [ ] Project ID is generated and visible
- [ ] No errors in console or `rank_tracker.log`
- [ ] Database records project in `projects` table
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT id, name FROM projects ORDER BY id DESC LIMIT 1'); print(c.fetchone())"
  ```

**Expected Result**: New project created with valid ID

---

### Test 1.2: Project Persistence
**Goal**: Verify project is saved and retrievable

**Steps**:
1. Restart application
2. Check if project still appears in list
3. Select project and verify name is correct

**Verify**:
- [ ] Project persists after restart
- [ ] All project fields match what was entered
- [ ] Session correctly loads project context

**Expected Result**: Project state fully preserved

---

## PHASE 2: CONFIGURATION & DATA ENTRY

### Test 2.1: Add Business Name(s)
**Goal**: Verify business name management

**Steps**:
1. In project settings, add business name: "Test Business"
2. Add alias: "Test Company"
3. Add another variation: "TB Services"
4. Save

**Verify**:
- [ ] All business names display in UI
- [ ] Names are stored in database in projects.business_names JSON
  ```bash
  python -c "import sqlite3, json; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT business_names FROM projects WHERE name=\"E2E Test Project\"'); names=json.loads(c.fetchone()[0]); print(names)"
  ```
- [ ] Names can be edited/removed
- [ ] Database reflects changes immediately
- [ ] No errors in logs

**Expected Result**: All business names stored and retrievable

---

### Test 2.2: Add Keywords
**Goal**: Verify keyword management

**Steps**:
1. Add keyword: "keyword 1"
2. Add keyword: "keyword 2"
3. Add keyword: "keyword 3"
4. Save

**Verify**:
- [ ] All keywords display in UI
- [ ] Keywords stored in database (projects.keywords JSON)
  ```bash
  python -c "import sqlite3, json; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT keywords FROM projects WHERE name=\"E2E Test Project\"'); kw=json.loads(c.fetchone()[0]); print(kw)"
  ```
- [ ] Can edit/remove keywords
- [ ] Order is preserved
- [ ] No duplicates allowed (if applicable)

**Expected Result**: All keywords stored correctly

---

### Test 2.3: Add Website URL
**Goal**: Verify website configuration (NEW REQUIREMENT)

**Steps**:
1. In project settings, add website field: "https://example-business.com"
2. Save

**Verify**:
- [ ] Website field added to projects table (if not already)
- [ ] Website URL is stored and displayed
- [ ] URL is validated (basic: starts with http:// or https://)
- [ ] Website can be updated
- [ ] Website appears in project details

**Note**: This field should be used for landing page checking once feature is re-enabled

**Expected Result**: Website URL stored per project

---

### Test 2.4: Draw Service Area Polygon
**Goal**: Verify polygon drawing and storage

**Steps**:
1. Go to map interface
2. Click "Draw Polygon"
3. Draw a polygon with 4+ points around a test area
4. Save polygon

**Verify**:
- [ ] Polygon displays on map with correct visual
- [ ] Polygon coordinates are stored in database (saved_polygons table)
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM saved_polygons'); print(c.fetchone()[0])"
  ```
- [ ] Polygon persists after page reload
- [ ] Can edit/modify polygon points
- [ ] Bounding box calculated correctly from polygon
- [ ] Point-in-polygon logic works (test with known coordinates)

**Expected Result**: Polygon stored and usable for scan area definition

---

## PHASE 3: SCAN EXECUTION & API INTEGRATION

### Test 3.1: Start Scan
**Goal**: Verify scan initiation and job tracking

**Steps**:
1. Configure scan settings:
   - Grid spacing: 500m
   - Keywords: Select all added keywords
   - Area: Polygon from Phase 2.4
2. Click "Run Scan"

**Verify**:
- [ ] Scan job is created with unique ID
- [ ] Job ID appears in UI
- [ ] Job record created in database: `scans` table
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT id, project_id, status FROM scans ORDER BY id DESC LIMIT 1'); print(c.fetchone())"
  ```
- [ ] No immediate errors in `rank_tracker.log`
- [ ] Progress bar initializes
- [ ] "Running" status displayed

**Expected Result**: Scan job created and initialized

---

### Test 3.2: Grid Point Calculation
**Goal**: Verify grid generation matches configuration

**Steps**:
1. Monitor scan progress
2. Check `rank_tracker.log` for grid calculation messages
3. After scan, query database for grid points

**Verify**:
- [ ] Grid points are created based on polygon and spacing
- [ ] Points are stored in `scan_points` table
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM scan_points WHERE scan_id = (SELECT id FROM scans ORDER BY id DESC LIMIT 1)'); print(f'Grid points: {c.fetchone()[0]}')"
  ```
- [ ] Point coordinates are within polygon bounds
- [ ] Spacing matches configuration (500m = ~0.0045 degrees)
- [ ] No duplicate points

**Expected Result**: Grid points correctly calculated and stored

---

### Test 3.3: API Calls & Real Data Retrieval
**Goal**: Verify API integration is working with real data

**Steps**:
1. Monitor scan progress in UI
2. Watch `rank_tracker.log` for API call messages
3. Check for real competitor names (not "Competitor 1", etc.)

**Verify**:
- [ ] API calls are made (not dummy mode)
- [ ] Log shows: "🔴 Real API Call" messages
- [ ] Search results include real business names
- [ ] Local pack results include ratings/reviews
- [ ] Organic results include positions
- [ ] Response data has expected fields:
  ```
  - title/name
  - rating
  - reviews/review_count
  - address
  - position
  - website (if available)
  ```

**Check logs for**:
- [ ] No "Dummy mode" messages
- [ ] No "Cache-only" messages (unless explicitly testing cache)
- [ ] API key validation passed
- [ ] Status codes 200 for successful calls

**Expected Result**: Real API data retrieved successfully

---

### Test 3.4: Business Matching
**Goal**: Verify business name matching in results

**Steps**:
1. Monitor scan for results matching your business
2. Check logs for matching operations
3. Verify matched business appears with correct rank

**Verify**:
- [ ] Business names are searched case-insensitively
- [ ] Alias variations match (substring matching)
- [ ] Matched business is highlighted/identified
- [ ] Rank position is correctly extracted
- [ ] If business not found, status shows "not_found" (not error)

**Check database**:
```bash
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT matched_business_name, local_pack_rank, organic_rank FROM point_history LIMIT 5');
for row in c.fetchall(): print(row)"
```

**Expected Result**: Business matching works correctly

---

### Test 3.5: Progress Reporting
**Goal**: Verify real-time progress updates

**Steps**:
1. Start a scan
2. Watch progress bar in UI
3. Check terminal for progress messages
4. Monitor job status updates

**Verify**:
- [ ] Progress bar advances as points are processed
- [ ] Progress percentage increases (0% → 100%)
- [ ] ETA is displayed and updates
- [ ] Points completed counter increments
- [ ] No frozen/stuck progress
- [ ] Final status shows 100% completion

**Check logs for**:
- [ ] Job start message
- [ ] Point processing messages
- [ ] Job completion message
- [ ] No stalled messages

**Expected Result**: Progress accurately reported throughout scan

---

## PHASE 4: DATA PERSISTENCE & CACHING

### Test 4.1: Scan Point Data Storage
**Goal**: Verify all point-level data is saved

**Steps**:
1. After scan completes, query database

**Verify**:
- [ ] Each grid point has record in `scan_points`:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM scan_points WHERE scan_id = (SELECT id FROM scans ORDER BY id DESC LIMIT 1)'); print(f'Total points: {c.fetchone()[0]}')"
  ```
- [ ] Each point has:
  - [ ] scan_id (links to scan)
  - [ ] lat, lon (coordinates)
  - [ ] keyword (search keyword)
  - [ ] local_pack_rank (if found)
  - [ ] organic_rank (if found)
  - [ ] status (success/not_found/error)
  - [ ] timestamp

**Expected Result**: All point data persisted correctly

---

### Test 4.2: Competitor Data Storage
**Goal**: Verify competitor data is saved to both tables

**Steps**:
1. Query competitor_snapshots (current scan)
2. Query competitor_history (all-time tracking)

**Verify**:
- [ ] Competitors saved in `competitor_snapshots`:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_snapshots WHERE scan_point_id IN (SELECT id FROM scan_points WHERE scan_id = (SELECT id FROM scans ORDER BY id DESC LIMIT 1))'); print(f'Snapshot records: {c.fetchone()[0]}')"
  ```
- [ ] Competitors saved in `competitor_history`:
  ```bash
  python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_history WHERE project_id = (SELECT project_id FROM scans ORDER BY id DESC LIMIT 1)'); print(f'History records: {c.fetchone()[0]}')"
  ```
- [ ] competitor_history count > 0 (THIS WAS THE BUG - should be fixed now)
- [ ] No errors in `rank_tracker.log` about competitor saves

**Check fields**:
```bash
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT competitor_name, rank, review_count, rating_stars FROM competitor_snapshots LIMIT 3');
for row in c.fetchall(): print(row)"
```

**Verify**:
- [ ] competitor_name is real business name (not "Competitor 1")
- [ ] rank is 1-30
- [ ] review_count >= 0 (or NULL if not available)
- [ ] rating_stars is 0.0-5.0 (or NULL)

**Expected Result**: Competitors stored in both tables with valid data

---

### Test 4.3: Point History Storage
**Goal**: Verify point-level history is recorded

**Steps**:
1. Query `point_history` table

**Verify**:
- [ ] Records exist for each point scanned
- [ ] Fields include:
  - [ ] project_id, lat, lon, keyword
  - [ ] business_name (primary business)
  - [ ] matched_business_name (if found)
  - [ ] local_pack_rank, organic_rank, display_rank
  - [ ] scan_date, city

**Check**:
```bash
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT city, keyword, matched_business_name, local_pack_rank FROM point_history ORDER BY scan_date DESC LIMIT 5');
for row in c.fetchall(): print(row)"
```

**Verify**:
- [ ] city is actual city name (not coordinates)
- [ ] keyword matches what was searched
- [ ] matched_business_name is either your business or NULL
- [ ] Ranks are numbers or NULL

**Expected Result**: Complete point-level history recorded

---

### Test 4.4: Cache Creation
**Goal**: Verify API responses are cached

**Steps**:
1. After scan, check cache directory
2. Look at cached files

**Verify**:
- [ ] Cache files created: `cache/*.json`
- [ ] File count > 0
  ```bash
  ls -la c:\zap\rank-tracker\cache | wc -l
  ```
- [ ] Files are valid JSON
  ```bash
  python -c "import json;
  import os
  cache_files = [f for f in os.listdir('cache') if f.endswith('.json')]
  print(f'Cache files: {len(cache_files)}')
  for f in cache_files[:1]:
      with open(f'cache/{f}') as fp:
          data = json.load(fp)
          print(f'File {f[:8]}... is valid JSON')"
  ```

**Check file contents**:
```bash
python -c "import json, os
files = [f for f in os.listdir('cache') if f.endswith('.json')]
if files:
    with open(f'cache/{files[0]}') as f:
        data = json.load(f)
        if 'searchParameters' in data:
            print('Search params:', data['searchParameters'].get('q'))
        if 'places' in data:
            print('Places count:', len(data['places']))"
```

**Verify**:
- [ ] Cache contains `searchParameters` with query
- [ ] Cache contains `places` or `organic` results
- [ ] Results match what was returned in scan

**Expected Result**: API responses cached successfully

---

### Test 4.5: Cache-Only Rescan
**Goal**: Verify cached data can be reused without new API calls

**Steps**:
1. Run a second scan with:
   - Same keywords
   - Same area
   - WITH cache enabled
2. Monitor for cache hits

**Verify**:
- [ ] Scan completes much faster (no API latency)
- [ ] Log shows "🟢 Loaded from Cache" messages
- [ ] Results match previous scan
- [ ] No new API calls made
- [ ] Cache hit counter increments

**Check logs**:
```bash
tail -n 50 rank_tracker.log | grep "Loaded from Cache"
```

**Expected Result**: Cache-only scan works correctly

---

## PHASE 5: UI/DATA VISUALIZATION

### Test 5.1: Dashboard Display
**Goal**: Verify scan results display in dashboard

**Steps**:
1. Complete a scan
2. Navigate to Dashboard
3. View scan summary

**Verify**:
- [ ] Scan appears in scan history
- [ ] Scan date/time correct
- [ ] Number of points processed shown correctly
- [ ] Keywords listed
- [ ] Scan status shows "Complete"
- [ ] No error messages displayed

**Check elements**:
- [ ] Scan name/ID visible
- [ ] Total points: matches grid point count
- [ ] Keywords: matches what was configured
- [ ] Competitors found: > 0

**Expected Result**: Dashboard shows accurate scan summary

---

### Test 5.2: Map Display
**Goal**: Verify scan points display on map

**Steps**:
1. Open Map tab for the scan
2. Zoom and pan around

**Verify**:
- [ ] Polygon drawn area is visible
- [ ] Grid points visible as markers/dots
- [ ] Point count matches database
- [ ] Colors represent status:
  - [ ] Green = success (found)
  - [ ] Red = not found
  - [ ] Yellow/Orange = warning/partial
  - [ ] Gray = error

**Interact with map**:
- [ ] Click on point shows details
- [ ] Details popup shows:
  - [ ] Coordinates
  - [ ] Keyword
  - [ ] Business rank
  - [ ] Status

**Expected Result**: All scan points displayed correctly on map

---

### Test 5.3: Point Details View
**Goal**: Verify individual point data display

**Steps**:
1. Click on a grid point on map
2. View point details panel/modal

**Verify**:
- [ ] Coordinates displayed (lat, lon)
- [ ] Keyword shown
- [ ] City/location shown
- [ ] Business name shown (if found)
- [ ] Local pack rank shown
- [ ] Organic rank shown
- [ ] Competitors list shows (top 3-10)
- [ ] Status indicator clear

**Check competitor details in point**:
- [ ] Competitor names are real
- [ ] Ranks are reasonable (1-30)
- [ ] Ratings/reviews shown if available
- [ ] No "Competitor 1", "Competitor 2"

**Expected Result**: Point details complete and accurate

---

### Test 5.4: Competitors Tab
**Goal**: Verify competitor aggregation and display

**Steps**:
1. Navigate to Competitors tab/page
2. View competitor list

**Verify**:
- [ ] Competitor list populated (count > 0)
- [ ] Each competitor shows:
  - [ ] Name (real business name)
  - [ ] Times ranked (count)
  - [ ] Dominance score
  - [ ] Average rank
  - [ ] Top rank achieved
  - [ ] Address (if available)
  - [ ] Phone (if available)
  - [ ] Website (if available)

**Check data**:
```bash
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT competitor_name, COUNT(*) as count FROM competitor_history GROUP BY competitor_name ORDER BY count DESC LIMIT 5');
for name, cnt in c.fetchall(): print(f'{name}: {cnt} times')"
```

**Verify**:
- [ ] Competitors listed match database
- [ ] Counts are accurate
- [ ] Names are real (not "Competitor X")

**Sort/filter tests**:
- [ ] Sort by name (A-Z, Z-A)
- [ ] Sort by rank count (most → least)
- [ ] Sort by dominance score
- [ ] Filter by keyword (if available)

**Expected Result**: Competitor data aggregated and displayed correctly

---

### Test 5.5: Charts & Analytics
**Goal**: Verify visual analytics work

**Steps**:
1. View dashboard charts
2. Check rank distribution
3. View competitor dominance chart

**Verify**:
- [ ] Rank distribution chart displays
  - [ ] Y-axis shows frequency
  - [ ] X-axis shows ranks (1-30)
  - [ ] Bar heights match data
- [ ] Competitor chart shows
  - [ ] Top competitors highlighted
  - [ ] Dominance scores accurate
  - [ ] Interactive (hover shows details)

**Expected Result**: Charts render correctly with accurate data

---

### Test 5.6: Rankings Table
**Goal**: Verify detailed ranking table display

**Steps**:
1. View Rankings or Results table
2. Check all columns populate

**Verify**:
- [ ] Table shows all scanned points
- [ ] Columns include:
  - [ ] Point ID / Coordinates
  - [ ] Keyword
  - [ ] City
  - [ ] Business Rank (Local)
  - [ ] Business Rank (Organic)
  - [ ] Status
  - [ ] Competitors Found (count)
  - [ ] Scan Date

**Test table features**:
- [ ] Sort by column (ascending/descending)
- [ ] Search/filter by keyword
- [ ] Pagination works (if >25 rows)
- [ ] Export to CSV (if available)
- [ ] Click row → shows point details

**Check data accuracy**:
```bash
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT keyword, local_pack_rank, organic_rank, status FROM point_history ORDER BY scan_date DESC LIMIT 10');
for row in c.fetchall(): print(row)"
```

**Verify**:
- [ ] Ranks match database
- [ ] Status matches database
- [ ] Keywords match configuration

**Expected Result**: Rankings table complete and sortable

---

## PHASE 6: DATA INTEGRITY & ANALYTICS

### Test 6.1: Run Admin Integrity Check
**Goal**: Verify all data is consistent

**Steps**:
```bash
cd c:\zap\rank-tracker
python admin_cleanup.py --check
```

**Verify output shows**:
- [ ] projects: 1+ rows ✓
- [ ] scans: 1+ rows ✓
- [ ] scan_points: >0 rows ✓
- [ ] point_history: >0 rows ✓
- [ ] competitor_snapshots: >0 rows ✓
- [ ] competitor_history: >0 rows ✓ **(THIS WAS THE KEY BUG - MUST BE FIXED)**
- [ ] No warnings about missing data

**Expected Result**: Database integrity verified

---

### Test 6.2: Verify No Dummy Data
**Goal**: Confirm no fake competitor data exists

**Steps**:
```bash
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_history WHERE competitor_name LIKE \"Competitor %\"'); print(f'Fake competitors: {c.fetchone()[0]}')"
```

**Verify**:
- [ ] Result: 0 (no fake competitors)
- [ ] All competitors are real business names
- [ ] No "Competitor 1", "Competitor 2", etc.

**Expected Result**: Only real competitor data in database

---

### Test 6.3: Verify Correct Geographic Data
**Goal**: Confirm cache has correct location data

**Steps**:
1. Check cache file contents
2. Verify location in search parameters

**Verify**:
```bash
python -c "import json, os
files = [f for f in os.listdir('cache') if f.endswith('.json')]
locations = set()
for f in files[:10]:
    with open(f'cache/{f}') as fp:
        data = json.load(fp)
        if 'searchParameters' in data:
            loc = data['searchParameters'].get('location', 'unknown')
            locations.add(str(loc)[:50])
for loc in locations:
    print(f'Location: {loc}')"
```

**Verify**:
- [ ] Locations match your polygon area
- [ ] No Rome, Milano, Torino, Naples data
- [ ] No data from wrong geographic regions

**Expected Result**: All cached data from correct locations

---

### Test 6.4: Verify Logging Works
**Goal**: Confirm error logging is functional

**Steps**:
1. Check `rank_tracker.log` file exists
2. Review log contents

**Verify**:
```bash
head -20 c:\zap\rank-tracker\rank_tracker.log
```

- [ ] Log file created
- [ ] Contains timestamps
- [ ] Contains INFO messages (scan start, etc.)
- [ ] Contains API messages
- [ ] Contains completion message
- [ ] Format: `YYYY-MM-DD HH:MM:SS,mmm - module - LEVEL - message`
- [ ] No Python exceptions/errors (unless expected)

**Expected Result**: Logging properly configured and functional

---

### Test 6.5: Run Second Complete Scan
**Goal**: Verify system can handle multiple scans

**Steps**:
1. Create new project or use existing
2. Run another complete scan
3. Verify data accumulates correctly

**Verify**:
- [ ] New scan has different ID
- [ ] Previous scan data still intact
- [ ] No data corruption between scans
- [ ] Database row counts increase appropriately
- [ ] Can view both scans independently

**Expected Result**: Multiple scans work correctly

---

## PHASE 7: ERROR HANDLING & EDGE CASES

### Test 7.1: Empty Results Handling
**Goal**: Verify system handles "not found" scenarios

**Steps**:
1. Search for a keyword that likely won't find your business
2. Verify graceful handling

**Verify**:
- [ ] Scan completes without crashing
- [ ] Point status shows "not_found"
- [ ] No error messages in logs
- [ ] Competitor list is empty for that point (not errored)
- [ ] Database records the "not found" state

**Expected Result**: Empty results handled gracefully

---

### Test 7.2: API Error Handling
**Goal**: Verify system handles API failures gracefully

**Steps**:
1. Temporarily disable API key in .env (test)
2. Run a small scan
3. Monitor error handling
4. Restore API key

**Verify**:
- [ ] Scan marks points as "error" (not "not_found")
- [ ] Log shows API error message
- [ ] Scan doesn't crash
- [ ] Error message is helpful
- [ ] User is informed of the error

**Expected Result**: API errors handled appropriately

---

### Test 7.3: Database Constraint Violations
**Goal**: Verify database integrity constraints work

**Steps**:
1. Monitor for any database errors during normal operation
2. Check if constraints prevent bad data

**Verify**:
- [ ] No duplicate scan_points with same coordinates
- [ ] No orphaned competitor records
- [ ] Foreign key relationships maintained
- [ ] Required fields always populated

**Expected Result**: Database constraints enforced

---

## CHECKLIST - SUMMARY

### Must Pass
- [ ] **Phase 1**: Project created and persists
- [ ] **Phase 2**: All configuration data stored (names, keywords, website, polygon)
- [ ] **Phase 3**: Scan executes with real API calls (not dummy)
- [ ] **Phase 4**: All data persisted to database with no errors
- [ ] **Phase 4**: competitor_history has records (>0) ← **KEY BUG FIX**
- [ ] **Phase 4**: No "Competitor 1" fake data
- [ ] **Phase 4**: Cache created with correct locations
- [ ] **Phase 5**: Dashboard displays accurate scan summary
- [ ] **Phase 5**: Map shows all grid points correctly
- [ ] **Phase 5**: Competitors tab shows real business names
- [ ] **Phase 5**: All tables and charts display correctly
- [ ] **Phase 6**: Admin check shows all tables populated
- [ ] **Phase 6**: Logging works and errors are recorded
- [ ] **Phase 7**: Error handling works for edge cases

### Critical Indicators
1. **competitor_history count > 0** ← Main bug fix validation
2. **No "Competitor 1", "Competitor 2" fake names**
3. **All locations from correct geographic area**
4. **rank_tracker.log has no ERROR entries for normal scans**
5. **Table data matches database queries exactly**

---

## EXECUTING THE TEST

### Recommended Order
1. **Morning**: Run Phases 1-3 (setup + scan)
2. **Mid-morning**: Run Phase 4 (data verification)
3. **Afternoon**: Run Phase 5 (UI checks)
4. **End of day**: Run Phase 6 (integrity)
5. **Next day**: Run Phase 7 (edge cases) + Phase 6.5 (second scan)

### Testing Tools
```bash
# Check logs in real-time
tail -f rank_tracker.log

# Run integrity check
python admin_cleanup.py --check

# Database queries
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); ..."

# Check cache
ls cache/ | wc -l

# Verify no dummy data
python -c "import sqlite3; conn=sqlite3.connect('scans.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM competitor_history WHERE competitor_name LIKE \"Competitor %\"'); print(c.fetchone())"
```

---

## EXPECTED RESULTS

After **complete** execution of all phases:

✅ Project created with name, keywords, business names, website, polygon
✅ Scan executed with real API calls
✅ 100+ grid points processed
✅ 500+ competitor snapshot records
✅ 1000+ competitor history records ← **Must be > 0!**
✅ All map points display correctly
✅ All competitors show real business names
✅ Dashboard shows accurate summary
✅ Tables and charts render correctly
✅ Logs show clean execution with no errors
✅ Cache contains only correct location data
✅ Database integrity check passes

---

## Success Criteria

**The system passes E2E testing when**:

1. **Data Pipeline**: User input → Grid → API → Database → UI (all steps work)
2. **Data Quality**: No fake data, no wrong locations, only real competitors
3. **Persistence**: All data survives app restart
4. **Logging**: All errors are logged and visible
5. **Performance**: Scans complete in reasonable time
6. **User Experience**: Every UI element displays correct data

---

**Test Status**: Ready to execute
**Expected Duration**: 4-6 hours of thorough testing
**Tester Role**: Validate every single row, card, and chart

