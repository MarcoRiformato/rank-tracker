#!/usr/bin/env python3
"""
Real Business Test - Edil Italia di Sergio Fuscaldo
Keywords: ristrutturazioni saronno, ristrutturazione bagno, ristrutturazione tetto
Service Area: 25km radius around Saronno with 5km grid spacing
"""

import sqlite3
import json
import requests
import hashlib
import os
import math
from datetime import datetime
import time

print("=" * 80)
print("REAL BUSINESS TEST - EDIL ITALIA DI SERGIO FUSCALDO")
print("=" * 80)
print()

# Configuration
SARONNO_CENTER = (45.3156, 8.8563)
RADIUS_KM = 25
GRID_SPACING_KM = 5
BUSINESS_NAMES = ["Edil Italia di Sergio Fuscaldo", "Sergio Fuscaldo", "Edilitalia"]
KEYWORDS = ["ristrutturazioni saronno", "ristrutturazione bagno", "ristrutturazione tetto"]
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
DB_NAME = 'scans.db'

print(f"Configuration:")
print(f"  Business: {', '.join(BUSINESS_NAMES)}")
print(f"  Keywords: {', '.join(KEYWORDS)}")
print(f"  Service Center: {SARONNO_CENTER}")
print(f"  Search Radius: {RADIUS_KM}km")
print(f"  Grid Spacing: {GRID_SPACING_KM}km")
print()

# Generate grid points
def generate_grid_points(center_lat, center_lon, radius_km, spacing_km):
    """Generate grid points within radius of center"""
    points = []

    # Convert to degrees (rough approximation)
    lat_spacing = spacing_km / 111.0  # 1 degree latitude ≈ 111km
    lon_spacing = spacing_km / (111.0 * math.cos(math.radians(center_lat)))

    # Create grid
    lat = center_lat - (radius_km / 111.0)
    lat_max = center_lat + (radius_km / 111.0)

    while lat <= lat_max:
        lon = center_lon - (radius_km / (111.0 * math.cos(math.radians(lat))))
        lon_max = center_lon + (radius_km / (111.0 * math.cos(math.radians(lat))))

        while lon <= lon_max:
            # Check if point is within radius
            dlat = (lat - center_lat) * 111.0
            dlon = (lon - center_lon) * 111.0 * math.cos(math.radians(lat))
            distance = math.sqrt(dlat**2 + dlon**2)

            if distance <= radius_km:
                points.append((round(lat, 4), round(lon, 4)))

            lon += lon_spacing

        lat += lat_spacing

    return points

print("TEST 1: Generate Grid Points")
print("-" * 80)

grid_points = generate_grid_points(SARONNO_CENTER[0], SARONNO_CENTER[1], RADIUS_KM, GRID_SPACING_KM)
print(f"[OK] Generated {len(grid_points)} grid points")
print(f"     Bounding area: ~{RADIUS_KM}km radius, ~{GRID_SPACING_KM}km spacing")

# Show sample points
print(f"\nSample grid points (first 5):")
for i, (lat, lon) in enumerate(grid_points[:5]):
    print(f"  {i+1}. ({lat}, {lon})")
print()

# Create project
print("TEST 2: Create Project")
print("-" * 80)

try:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    project_data = {
        'name': 'Real Business Test - Edil Italia',
        'business_names': json.dumps(BUSINESS_NAMES),
        'keywords': json.dumps(KEYWORDS),
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

    c.execute('''
        INSERT INTO projects (name, business_names, keywords, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (project_data['name'], project_data['business_names'],
          project_data['keywords'], project_data['created_at'],
          project_data['updated_at']))

    project_id = c.lastrowid
    conn.commit()

    print(f"[OK] Project created with ID: {project_id}")
    print(f"     Name: {project_data['name']}")

except Exception as e:
    print(f"[ERROR] Failed to create project: {e}")
    exit(1)

print()

# Create scans for each keyword
print("TEST 3: Create Scan Records")
print("-" * 80)

scan_ids = []
try:
    for keyword in KEYWORDS:
        c.execute('''
            INSERT INTO scans (project_id, date, business_name, keyword, grid_spacing,
                             bbox_north, bbox_east, bbox_south, bbox_west)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, datetime.now().isoformat(),
              ', '.join(BUSINESS_NAMES[:2]),
              keyword, GRID_SPACING_KM,
              SARONNO_CENTER[0] + RADIUS_KM/111.0,
              SARONNO_CENTER[1] + RADIUS_KM/(111.0*math.cos(math.radians(SARONNO_CENTER[0]))),
              SARONNO_CENTER[0] - RADIUS_KM/111.0,
              SARONNO_CENTER[1] - RADIUS_KM/(111.0*math.cos(math.radians(SARONNO_CENTER[0])))))

        scan_ids.append(c.lastrowid)
        print(f"[OK] Scan created for keyword: '{keyword}' (ID: {c.lastrowid})")

    conn.commit()

except Exception as e:
    print(f"[ERROR] Failed to create scans: {e}")
    exit(1)

print()
print("TEST 4: Test Configuration Summary")
print("-" * 80)

total_api_calls = len(grid_points) * len(KEYWORDS)
print(f"[OK] Test configuration ready:")
print(f"     Project ID: {project_id}")
print(f"     Grid points: {len(grid_points)}")
print(f"     Keywords: {len(KEYWORDS)}")
print(f"     Total potential API calls: {total_api_calls}")
print(f"     With caching: First run ~{total_api_calls*7//60}-{total_api_calls*10//60} minutes")
print()

# Explain what happens next
print("=" * 80)
print("TEST SETUP COMPLETE")
print("=" * 80)
print()
print("Next steps:")
print()
print("1. REAL EXECUTION:")
print("   Use the web UI to create a scan with these settings:")
print(f"   - Project: {project_id}")
print(f"   - Service area: {RADIUS_KM}km radius around Saronno")
print(f"   - Keywords: {', '.join(KEYWORDS)}")
print()
print("2. OR RUN VIA API:")
print(f"   POST to /api/check-rankings with:")
print(f"   {{")
print(f"     'project_id': {project_id},")
print(f"     'keywords': {json.dumps(KEYWORDS)},")
print(f"     'polygon': null,")
print(f"     'grid_spacing': {GRID_SPACING_KM},")
print(f"     'service_center': {list(SARONNO_CENTER)},")
print(f"     'radius': {RADIUS_KM}")
print(f"   }}")
print()
print("3. MONITOR EXECUTION:")
print("   tail -f rank_tracker.log")
print()
print("4. VERIFY RESULTS:")
print("   python3 verify_system.py")
print()
print("Expected Results:")
print("  - Your business found in multiple locations")
print("  - local_pack_rank and organic_rank populated")
print("  - 5-15 competitors per location discovered")
print("  - All rich data: ratings, reviews, addresses, phones")
print("  - Duplicates deduplicated (no name variations)")
print()
print("Database files will be updated:")
print(f"  - scans: {len(scan_ids)} new records")
print(f"  - scan_points: ~{len(grid_points) * len(KEYWORDS)} new records")
print(f"  - competitors: ~{len(grid_points) * len(KEYWORDS) * 5}-{len(grid_points) * len(KEYWORDS) * 15} new records")
print()

conn.close()

print("=" * 80)
print("READY FOR TESTING")
print("=" * 80)
