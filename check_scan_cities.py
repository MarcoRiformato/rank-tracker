import sqlite3
from datetime import datetime

DB_NAME = 'scans.db'

def check_scan_cities():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Get latest scan date
    c.execute("SELECT MAX(date) FROM scans")
    latest_scan = c.fetchone()[0]
    print(f"Latest Scan Date: {latest_scan}")
    
    if not latest_scan:
        print("No scans found.")
        conn.close()
        return

    # 2. Check cities in point_history (where we searched)
    print("\n--- Cities in Scan Points (Target Locations) ---")
    c.execute('''
        SELECT city, COUNT(*) 
        FROM point_history 
        WHERE scan_date >= datetime(?, '-1 hour')
        GROUP BY city 
        ORDER BY COUNT(*) DESC
    ''', (latest_scan,))
    rows = c.fetchall()
    for row in rows:
        print(f"{row[0]}: {row[1]} points")

    # 3. Check cities in competitor_history (where results came from)
    print("\n--- Cities in Competitor Results (Found Business Locations) ---")
    c.execute('''
        SELECT city, COUNT(*) 
        FROM competitor_history 
        WHERE scan_date >= datetime(?, '-1 hour')
        GROUP BY city 
        ORDER BY COUNT(*) DESC
    ''', (latest_scan,))
    rows = c.fetchall()
    
    if not rows:
        print("No competitors found in history for this scan.")
    else:
        for row in rows:
            print(f"{row[0]}: {row[1]} records")
            
    # 4. Check total points vs filtered points
    c.execute('''
        SELECT COUNT(*) FROM scan_points 
        WHERE scan_id IN (SELECT id FROM scans WHERE date = ?)
    ''', (latest_scan,))
    total_points = c.fetchone()[0]
    print(f"\nTotal Scan Points: {total_points}")

    conn.close()

if __name__ == "__main__":
    check_scan_cities()
