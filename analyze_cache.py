import os
import json
import sqlite3
import time
from datetime import datetime

DB_PATH = 'scans.db'
CACHE_DIR = 'cache'

def get_latest_polygon():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT coordinates FROM saved_polygons ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception as e:
        print(f"Error fetching polygon: {e}")
    return None

def is_point_in_polygon(point, polygon):
    # point is (lat, lon), polygon is list of (lat, lon)
    x, y = point
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def analyze_cache():
    polygon = get_latest_polygon()
    if not polygon:
        print("No polygon found in database.")
        return

    print(f"Polygon found with {len(polygon)} points.")
    
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
    total_files = len(files)
    
    total_businesses = 0
    in_polygon_businesses = 0
    out_polygon_businesses = 0
    
    far_cities = {} # Track cities that are far away

    print(f"Scanning {total_files} cache files for COMPETITOR locations...")

    for filename in files:
        filepath = os.path.join(CACHE_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check 'places' list
            if 'places' in data and isinstance(data['places'], list):
                for place in data['places']:
                    total_businesses += 1
                    
                    # Check if place has coordinates
                    if 'latitude' in place and 'longitude' in place:
                        lat = place['latitude']
                        lon = place['longitude']
                        
                        if is_point_in_polygon((lat, lon), polygon):
                            in_polygon_businesses += 1
                        else:
                            out_polygon_businesses += 1
                            # Extract city from address if possible for stats
                            address = place.get('address', '')
                            if 'Roma' in address: far_cities['Roma'] = far_cities.get('Roma', 0) + 1
                            elif 'Milano' in address: far_cities['Milano'] = far_cities.get('Milano', 0) + 1
                            elif 'Torino' in address: far_cities['Torino'] = far_cities.get('Torino', 0) + 1
                            elif 'Napoli' in address: far_cities['Napoli'] = far_cities.get('Napoli', 0) + 1
                            
            # Check 'organic' list (usually no coords, but check snippet/title for city names?)
            # Organic usually doesn't have lat/lon in Serper standard response, so we skip for strict geo-check
            
        except Exception as e:
            # print(f"Error reading {filename}: {e}")
            pass

    print("-" * 30)
    print(f"Total Businesses Found in Cache: {total_businesses}")
    print(f"✅ Inside Polygon: {in_polygon_businesses}")
    print(f"❌ Outside Polygon: {out_polygon_businesses}")
    
    if out_polygon_businesses > 0:
        print("\nMajor Outliers Detected:")
        for city, count in far_cities.items():
            print(f"  - {city}: {count} occurrences")
            
    print("-" * 30)

if __name__ == "__main__":
    analyze_cache()
