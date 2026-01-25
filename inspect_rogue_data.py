import sqlite3
import json

DB_NAME = 'scans.db'

def inspect_rogue_data():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Check for competitors with unexpected cities (Palermo, Roma, Torino, Bologna found in user report)
    # We'll just look for anything that is likely "out of polygon" (assuming Saronno area)
    # Let's list top 20 cities found in the history
    print("--- Top 20 Cities in Competitor History ---")
    c.execute('''
        SELECT city, count(*) as cnt 
        FROM competitor_history 
        GROUP BY city 
        ORDER BY cnt DESC 
        LIMIT 20
    ''')
    for row in c.fetchall():
        print(f"{row[0]}: {row[1]}")

    # 2. Inspect detailed record for a "Roma" or "Palermo" entry
    print("\n--- Detailed Inspection of a Rogue Entry ---")
    c.execute('''
        SELECT competitor_name, city, address, rank, scan_date
        FROM competitor_history 
        WHERE city IN ('Roma', 'Palermo', 'Torino', 'Bologna')
        LIMIT 3
    ''')
    rows = c.fetchall()
    for row in rows:
        print(f"Name: {row[0]}, City: {row[1]}, Addr: {row[2]}, Rank: {row[3]}")
        
    conn.close()

if __name__ == "__main__":
    inspect_rogue_data()
