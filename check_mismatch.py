import sqlite3

DB_NAME = 'scans.db'

def check_address_city_mismatch():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Find records where city is likely local (from top list) but address contains "Roma" or "Palermo"
    # We'll search for address keywords in records linked to 'Parabiago' or 'Saronno' or similar
    
    print("Checking for address/city mismatches...")
    
    suspicious_cities = ['Roma', 'Palermo', 'Torino', 'Bologna', 'Napoli']
    
    for bad_city in suspicious_cities:
        c.execute(f'''
            SELECT count(*) 
            FROM competitor_history 
            WHERE address LIKE '% {bad_city} %' 
            AND city NOT LIKE '%{bad_city}%'
        ''')
        count = c.fetchone()[0]
        if count > 0:
            print(f"Found {count} records with '{bad_city}' in address but NOT in city column.")
            
            # Show example
            c.execute(f'''
                SELECT competitor_name, city, address, rank
                FROM competitor_history 
                WHERE address LIKE '% {bad_city} %' 
                AND city NOT LIKE '%{bad_city}%'
                LIMIT 1
            ''')
            row = c.fetchone()
            print(f"  Example: Name='{row[0]}', City='{row[1]}', Address='{row[2]}'")

    conn.close()

if __name__ == "__main__":
    check_address_city_mismatch()
