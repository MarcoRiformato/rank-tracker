import sqlite3

DB_NAME = 'scans.db'

def wipe_results():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    tables_to_clear = [
        'competitor_snapshots',
        'competitor_history',
        'point_history',
        'scan_points',
        'scans'
    ]
    
    print("Starting data wipe...")
    
    for table in tables_to_clear:
        try:
            c.execute(f"DELETE FROM {table}")
            print(f"Cleared table: {table} ({c.rowcount} records)")
        except sqlite3.OperationalError as e:
            print(f"Error checking {table}: {e}")

    conn.commit()
    
    # Verify project is still there
    c.execute("SELECT count(*) FROM projects")
    project_count = c.fetchone()[0]
    print(f"\nProjects remaining: {project_count}")
    
    c.execute("SELECT count(*) FROM saved_polygons")
    try:
        polygon_count = c.fetchone()[0]
        print(f"Saved polygons remaining: {polygon_count}")
    except:
        print("Could not check saved_polygons (might not exist yet)")

    conn.close()
    print("\nWipe complete. You can now run a fresh scan.")

if __name__ == "__main__":
    wipe_results()
