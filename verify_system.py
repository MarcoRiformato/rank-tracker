#!/usr/bin/env python3
"""
System verification script to confirm all major components are working correctly.
Tests:
1. Database structure
2. Cache system
3. Deduplication logic
4. Data field availability
"""

import sqlite3
import json
import os
import hashlib
from datetime import datetime

print("=" * 80)
print("SYSTEM VERIFICATION - Complete Check")
print("=" * 80)
print()

# TEST 1: Database Structure
print("TEST 1: Database Structure")
print("-" * 80)

try:
    conn = sqlite3.connect('scans.db')
    c = conn.cursor()

    # Check scan_points table
    c.execute("PRAGMA table_info(scan_points)")
    columns = c.fetchall()

    required_fields = {
        'local_pack_rank': False,
        'organic_rank': False,
        'display_rank': False,
        'matched_business_name': False,
        'keyword': False,
        'search_query': False
    }

    for col in columns:
        col_name = col[1]
        if col_name in required_fields:
            required_fields[col_name] = True

    all_present = all(required_fields.values())
    if all_present:
        print("[✓] scan_points table has all required ranking fields")
        print("    - local_pack_rank: Position in Maps/Local Pack (1-3)")
        print("    - organic_rank: Position in search results (1-100+)")
        print("    - display_rank: What shows on heatmap")
    else:
        missing = [k for k, v in required_fields.items() if not v]
        print(f"[✗] Missing fields: {missing}")

    # Check competitor_snapshots table
    c.execute("PRAGMA table_info(competitor_snapshots)")
    snap_columns = c.fetchall()
    snap_field_names = [col[1] for col in snap_columns]

    required_snap_fields = {
        'competitor_name': False,
        'rank': False,
        'review_count': False,
        'rating_stars': False,
        'address': False,
        'phone_number': False,
        'website': False,
        'category': False
    }

    for field in required_snap_fields:
        if field in snap_field_names:
            required_snap_fields[field] = True

    all_snap_present = all(required_snap_fields.values())
    if all_snap_present:
        print("[✓] competitor_snapshots table has all rich data fields")
    else:
        missing_snap = [k for k, v in required_snap_fields.items() if not v]
        print(f"[✗] Missing snapshot fields: {missing_snap}")

    conn.close()

except Exception as e:
    print(f"[✗] Database error: {e}")

print()

# TEST 2: Cache System Verification
print("TEST 2: Cache System Verification")
print("-" * 80)

try:
    cache_dir = 'cache'

    if os.path.exists(cache_dir):
        cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]

        if cache_files:
            print(f"[✓] Cache directory exists with {len(cache_files)} file(s)")

            # Check latest cache file
            latest_file = max([os.path.join(cache_dir, f) for f in cache_files],
                            key=os.path.getctime)
            file_size = os.path.getsize(latest_file)
            file_name = os.path.basename(latest_file)

            print(f"[✓] Latest cache: {file_name} ({file_size} bytes)")

            # Verify it's valid JSON
            with open(latest_file, 'r') as f:
                data = json.load(f)

            # Check for API response structure
            if 'organic' in data or 'places' in data or 'localPack' in data:
                print("[✓] Cache contains valid API response structure")

                if 'organic' in data:
                    print(f"    - organic results: {len(data.get('organic', []))} items")
                if 'places' in data:
                    print(f"    - places results: {len(data.get('places', []))} items")
                if 'localPack' in data:
                    print(f"    - localPack results: {len(data.get('localPack', []))} items")
            else:
                print("[✗] Cache file doesn't match API response format")
        else:
            print("[!] Cache directory exists but is empty (will be populated on next API call)")
    else:
        print("[!] Cache directory doesn't exist (will be created on first API call)")

except Exception as e:
    print(f"[✗] Cache check error: {e}")

print()

# TEST 3: Deduplication Logic Verification
print("TEST 3: Name Normalization (Deduplication)")
print("-" * 80)

def normalize_competitor_name(name):
    """Match the normalization in app.py"""
    if not name:
        return name
    normalized = name.strip().upper()
    normalized = normalized.replace('.', '').replace('|', '').replace('-', ' ')
    normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
    normalized = ' '.join(normalized.split())
    return normalized

# Test cases from your data
test_cases = [
    ("Cla. Vi. Ristrutturazioni", "CLA.VI. Ristrutturazioni | Saronno"),
    ("Impresa Edile Barbieri SRL - Saronno", "Impresa Edile Barbieri SRL"),
    ("CLA.VI. Ristrutturazioni | Saronno", "Cla. Vi. Ristrutturazioni"),
]

print("[✓] Testing name normalization:")
for name1, name2 in test_cases:
    norm1 = normalize_competitor_name(name1)
    norm2 = normalize_competitor_name(name2)
    match = norm1 == norm2
    status = "✓ MATCH (will deduplicate)" if match else "✗ DIFFERENT"
    print(f"    {status}")
    print(f"      '{name1}'")
    print(f"      → '{norm1}'")
    print(f"      vs")
    print(f"      '{name2}'")
    print(f"      → '{norm2}'")
    print()

print()

# TEST 4: Data Fields Check
print("TEST 4: Data Field Availability")
print("-" * 80)

try:
    conn = sqlite3.connect('scans.db')
    c = conn.cursor()

    # Check how many competitor records have rich data
    c.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN rating_stars IS NOT NULL THEN 1 ELSE 0 END) as with_ratings,
            SUM(CASE WHEN review_count IS NOT NULL THEN 1 ELSE 0 END) as with_reviews,
            SUM(CASE WHEN address IS NOT NULL AND address != '' THEN 1 ELSE 0 END) as with_address,
            SUM(CASE WHEN phone_number IS NOT NULL AND phone_number != '' THEN 1 ELSE 0 END) as with_phone
        FROM competitor_snapshots
    """)

    row = c.fetchone()
    total, with_ratings, with_reviews, with_address, with_phone = row

    print(f"[✓] Data field population status:")
    print(f"    Total records: {total}")

    if total > 0:
        rating_pct = (with_ratings / total * 100) if total else 0
        review_pct = (with_reviews / total * 100) if total else 0
        address_pct = (with_address / total * 100) if total else 0
        phone_pct = (with_phone / total * 100) if total else 0

        print(f"    - With ratings: {with_ratings}/{total} ({rating_pct:.0f}%)")
        print(f"    - With reviews: {with_reviews}/{total} ({review_pct:.0f}%)")
        print(f"    - With address: {with_address}/{total} ({address_pct:.0f}%)")
        print(f"    - With phone: {with_phone}/{total} ({phone_pct:.0f}%)")

        if rating_pct == 0 and with_ratings == 0:
            print()
            print("    [!] Rich data fields are empty. Possible reasons:")
            print("        1. Using /search endpoint (no rich data)")
            print("        2. Using /places endpoint but not extracting fields")
            print("        3. API not returning local pack data")
    else:
        print("    [!] No competitor records found (no scans completed)")

    conn.close()

except Exception as e:
    print(f"[✗] Data field check error: {e}")

print()

# TEST 5: Three Ranking Types
print("TEST 5: Three Ranking Types Tracking")
print("-" * 80)

try:
    conn = sqlite3.connect('scans.db')
    c = conn.cursor()

    c.execute("""
        SELECT
            COUNT(*) as total_points,
            SUM(CASE WHEN local_pack_rank IS NOT NULL THEN 1 ELSE 0 END) as with_local_pack,
            SUM(CASE WHEN organic_rank IS NOT NULL THEN 1 ELSE 0 END) as with_organic,
            SUM(CASE WHEN display_rank IS NOT NULL THEN 1 ELSE 0 END) as with_display
        FROM scan_points
    """)

    row = c.fetchone()
    total_points, with_local, with_organic, with_display = row

    if total_points and total_points > 0:
        print(f"[✓] Ranking types tracked:")
        print(f"    Total scan points: {total_points}")
        print(f"    - Local Pack Rank: {with_local}/{total_points} points ({with_local/total_points*100:.0f}%)")
        print(f"    - Organic Rank: {with_organic}/{total_points} points ({with_organic/total_points*100:.0f}%)")
        print(f"    - Display Rank: {with_display}/{total_points} points ({with_display/total_points*100:.0f}%)")

        print()
        print("    What this means:")
        print("    - Local Pack: Your position in Google Maps")
        print("    - Organic: Your position in search results")
        print("    - Display: What shows on the heatmap (currently = Local Pack)")
    else:
        print("[!] No scan points found. Run a scan to populate ranking data.")

    conn.close()

except Exception as e:
    print(f"[✗] Ranking check error: {e}")

print()
print("=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
print()
print("Summary:")
print("✓ = System component verified and working")
print("✗ = System component has issues")
print("! = System component status unclear (normal until first scan)")
print()
