import sqlite3
import json

DB_NAME = 'scans.db'
PROJECT_ID = 2
KEYWORD_TO_REMOVE = "pizza"

def remove_keyword():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Get current keywords
    c.execute("SELECT keywords FROM projects WHERE id = ?", (PROJECT_ID,))
    row = c.fetchone()
    
    if not row:
        print(f"Project ID {PROJECT_ID} not found.")
        return

    keywords_json = row[0]
    if not keywords_json:
        print("No keywords found.")
        return

    try:
        keywords = json.loads(keywords_json)
    except json.JSONDecodeError:
        print("Error decoding JSON.")
        return

    print(f"Current keywords: {keywords}")

    # 2. Remove keyword
    if KEYWORD_TO_REMOVE in keywords:
        keywords.remove(KEYWORD_TO_REMOVE)
        new_keywords_json = json.dumps(keywords)
        
        # 3. Update database
        c.execute("UPDATE projects SET keywords = ? WHERE id = ?", (new_keywords_json, PROJECT_ID))
        conn.commit()
        print(f"SUCCESS: Removed '{KEYWORD_TO_REMOVE}'.")
        print(f"New keywords: {keywords}")
    else:
        print(f"Keyword '{KEYWORD_TO_REMOVE}' not found in list.")

    conn.close()

if __name__ == "__main__":
    remove_keyword()
