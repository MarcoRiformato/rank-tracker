import sqlite3
import json

DB_NAME = 'scans.db'

def check_parabiago():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get Parabiago competitors
    c.execute('''
        SELECT competitor_name, city, address 
        FROM competitor_history 
        WHERE city = 'Parabiago'
        LIMIT 5
    ''')
    rows = c.fetchall()
    
    print("Competitors in Parabiago:")
    for row in rows:
        print(row)
        
    conn.close()

if __name__ == "__main__":
    check_parabiago()
