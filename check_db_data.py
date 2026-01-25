import sqlite3

DB_NAME = 'scans.db'

def check_data():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check for "Roma" in competitor names
    c.execute("SELECT COUNT(*), COUNT(DISTINCT competitor_name) FROM competitor_history WHERE competitor_name LIKE '%Roma%'")
    row = c.fetchone()
    print(f"Found {row[0]} records for {row[1]} competitors with 'Roma' in the name.")

    # Check total records
    c.execute("SELECT COUNT(*) FROM competitor_history")
    total = c.fetchone()[0]
    print(f"Total historical records: {total}")
    
    conn.close()

if __name__ == "__main__":
    check_data()
