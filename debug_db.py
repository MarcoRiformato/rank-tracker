
import sqlite3

conn = sqlite3.connect('scans.db')
c = conn.cursor()

print("--- Data Inspection ---")
c.execute("SELECT id, city, lat, lon FROM point_history ORDER BY id DESC LIMIT 20")
rows = c.fetchall()
for r in rows:
    print(f"ID: {r[0]}, City: '{r[1]}', Lat: {r[2]}, Lon: {r[3]}")

print("\n--- Rows with comma in city ---")
c.execute("SELECT count(*) FROM point_history WHERE city LIKE '%,%'")
print(c.fetchone()[0])

print("\n--- Rows with NULL city ---")
c.execute("SELECT count(*) FROM point_history WHERE city IS NULL")
print(c.fetchone()[0])

conn.close()
