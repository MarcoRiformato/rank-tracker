import sqlite3
import json

DB_NAME = 'scans.db'

def check_polygon():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name, coordinates FROM saved_polygons")
    rows = c.fetchall()
    conn.close()

    print(f"Found {len(rows)} polygons.")
    for row in rows:
        name = row[0]
        coords_json = row[1]
        try:
            coords = json.loads(coords_json)
            print(f"Polygon '{name}': {len(coords)} points")
            print(f"Sample: {coords[:3]}")
        except:
            print(f"Polygon '{name}': Invalid JSON")

if __name__ == "__main__":
    check_polygon()
