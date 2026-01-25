import sqlite3
import json

DB_NAME = 'scans.db'

def check_project_keywords():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name, keywords, business_names FROM projects")
    projects = c.fetchall()
    conn.close()

    print(f"Found {len(projects)} projects:")
    for p in projects:
        pid, name, keywords_json, business_names_json = p
        print(f"Project ID: {pid}")
        print(f"Name: {name}")
        print(f"Keywords (Raw): {keywords_json}")
        print(f"Business Names (Raw): {business_names_json}")
        print("-" * 20)

if __name__ == "__main__":
    check_project_keywords()
