
import sqlite3
import requests
import time
import sys
import os

# Add parent directory to path to import app config if needed, but we'll just replicate basic config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_NAME = 'scans.db'

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def reverse_geocode(lat, lon):
    """Get city/town name from coordinates using Nominatim (OpenStreetMap)"""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
        headers = {'User-Agent': 'RankTracker/1.0'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.ok:
            data = response.json()
            address = data.get('address', {})
            # Try to get city, town, village, or neighborhood
            city = (address.get('city') or address.get('town') or 
                   address.get('village') or address.get('neighbourhood') or
                   address.get('suburb') or address.get('municipality'))
            return city
        return None
    except Exception as e:
        print(f"Error geocoding {lat}, {lon}: {e}")
        return None

def backfill_cities():
    print("Starting city backfill...")
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Find point_history entries where city looks like coordinates or is null
    # We look for ',' and '.' in the city field, assuming "lat, lon" format
    c.execute('''
        SELECT id, lat, lon, city FROM point_history 
        WHERE city IS NULL OR city LIKE '%,%' OR city = ''
    ''')
    
    rows = c.fetchall()
    print(f"Found {len(rows)} point_history entries to check/update.")
    
    updated_count = 0
    cache = {} # (lat, lon) -> city
    
    for row in rows:
        record_id, lat, lon, current_city = row
        
        # Round required for cache hit (points are doubles)
        lat_key = round(lat, 4)
        lon_key = round(lon, 4)
        
        if (lat_key, lon_key) in cache:
            city = cache[(lat_key, lon_key)]
        else:
            print(f"Geocoding {lat}, {lon}...")
            city = reverse_geocode(lat, lon)
            time.sleep(1.1) # Respect rate limit
            
            if city:
                cache[(lat_key, lon_key)] = city
            else:
                print(f"Could not resolve city for {lat}, {lon}")
                continue

        if city and city != current_city:
            c.execute('UPDATE point_history SET city = ? WHERE id = ?', (city, record_id))
            updated_count += 1
            if updated_count % 10 == 0:
                conn.commit()
                print(f"Updated {updated_count} records...")
    
    conn.commit()
    print(f"Finished updating point_history. Total updated: {updated_count}")
    
    # 2. Update competitor_history as well
    print("Updating competitor_history...")
    c.execute('''
        SELECT id, scan_point_id, city FROM competitor_history 
        WHERE city IS NULL OR city LIKE '%,%' OR city = ''
    ''')
    
    comp_rows = c.fetchall()
    print(f"Found {len(comp_rows)} competitor_history entries to check.")
    
    comp_updated = 0
    
    for row in comp_rows:
        comp_id, scan_point_id, current_city = row
        
        # Get lat/lon from scan_point via scan_point_id? No, we need to join or look up.
        # But wait, we might have already cached the city for this location if it corresponds to a point_history location?
        # Actually, competitor_history doesn't have lat/lon directly, it links to scan_points?
        # Let's check schema.
        # competitor_history has: associated with a scan_point_id.
        # We can look up the city from point_history if we can map scan_point_id -> point_history?
        # Or just look up lat/lon from scan_points table.
        
        # Get lat/lon from scan_points
        c.execute('SELECT lat, lon FROM scan_points WHERE id = ?', (scan_point_id,))
        pt_row = c.fetchone()
        
        if pt_row:
            lat, lon = pt_row
            lat_key = round(lat, 4)
            lon_key = round(lon, 4)
            
            if (lat_key, lon_key) in cache:
                city = cache[(lat_key, lon_key)]
                
                if city and city != current_city:
                    c.execute('UPDATE competitor_history SET city = ? WHERE id = ?', (city, comp_id))
                    comp_updated += 1
            else:
                # If not in cache, we might need to geocode (unlikely if point_history was comprehensive, 
                # but possible if competitor_history exists without point_history for some reason)
                 print(f"Geocoding competitor loc {lat}, {lon}...")
                 city = reverse_geocode(lat, lon)
                 time.sleep(1.1)
                 if city:
                     cache[(lat_key, lon_key)] = city
                     c.execute('UPDATE competitor_history SET city = ? WHERE id = ?', (city, comp_id))
                     comp_updated += 1
        
        if comp_updated % 50 == 0:
            conn.commit()
            
    conn.commit()
    print(f"Finished updating competitor_history. Total updated: {comp_updated}")
    conn.close()

if __name__ == "__main__":
    backfill_cities()
