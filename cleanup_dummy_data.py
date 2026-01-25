#!/usr/bin/env python3
"""
Script to remove all dummy/test data from the database.
This will remove data with known dummy patterns:
- Keywords: "pizza delivery", "italian restaurant", "food near me"
- Business names containing: "My Business", "My Business Inc", "My Business LLC"
"""

import sqlite3
import sys

DB_NAME = 'scans.db'

def cleanup_dummy_data():
    """Remove all dummy data from the database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Known dummy data patterns
    dummy_keywords = ['pizza delivery', 'italian restaurant', 'food near me']
    dummy_business_patterns = ['My Business', 'My Business Inc', 'My Business LLC']
    
    deleted_counts = {
        'scans': 0,
        'scan_points': 0,
        'point_history': 0,
        'competitor_snapshots': 0,
        'competitor_history': 0
    }
    
    try:
        print("Searching for dummy data...")
        
        # Find scan IDs with dummy keywords or business names (across all projects)
        dummy_scan_ids = []
        
        # Find scans with dummy keywords
        for keyword in dummy_keywords:
            c.execute('SELECT id FROM scans WHERE keyword = ?', (keyword,))
            found_ids = [row[0] for row in c.fetchall()]
            dummy_scan_ids.extend(found_ids)
            if found_ids:
                print(f"  Found {len(found_ids)} scans with keyword: '{keyword}'")
        
        # Find scans with dummy business names
        for pattern in dummy_business_patterns:
            c.execute('SELECT id FROM scans WHERE business_name LIKE ?', (f'%{pattern}%',))
            found_ids = [row[0] for row in c.fetchall()]
            dummy_scan_ids.extend(found_ids)
            if found_ids:
                print(f"  Found {len(found_ids)} scans with business name pattern: '{pattern}'")
        
        # Remove duplicates
        dummy_scan_ids = list(set(dummy_scan_ids))
        
        if not dummy_scan_ids:
            print("SUCCESS: No dummy data found!")
            conn.close()
            return
        
        print(f"\nDeleting {len(dummy_scan_ids)} dummy scans and associated data...")
        
        if dummy_scan_ids:
            # Delete competitor_snapshots for these scan points
            c.execute('''
                DELETE FROM competitor_snapshots 
                WHERE scan_point_id IN (
                    SELECT id FROM scan_points WHERE scan_id IN ({})
                )
            '''.format(','.join(['?' for _ in dummy_scan_ids])), dummy_scan_ids)
            deleted_counts['competitor_snapshots'] = c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} competitor snapshots")
            
            # Delete competitor_history for these scan points
            c.execute('''
                DELETE FROM competitor_history 
                WHERE scan_point_id IN (
                    SELECT id FROM scan_points WHERE scan_id IN ({})
                )
            '''.format(','.join(['?' for _ in dummy_scan_ids])), dummy_scan_ids)
            deleted_counts['competitor_history'] = c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} competitor history entries")
            
            # Delete scan_points
            c.execute('DELETE FROM scan_points WHERE scan_id IN ({})'.format(','.join(['?' for _ in dummy_scan_ids])), dummy_scan_ids)
            deleted_counts['scan_points'] = c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} scan points")
            
            # Delete scans
            c.execute('DELETE FROM scans WHERE id IN ({})'.format(','.join(['?' for _ in dummy_scan_ids])), dummy_scan_ids)
            deleted_counts['scans'] = c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} scans")
        
        # Also delete point_history entries with dummy keywords or business names
        for keyword in dummy_keywords:
            c.execute('DELETE FROM point_history WHERE keyword = ?', (keyword,))
            deleted_counts['point_history'] += c.rowcount
        
        for pattern in dummy_business_patterns:
            c.execute('DELETE FROM point_history WHERE business_name LIKE ?', (f'%{pattern}%',))
            deleted_counts['point_history'] += c.rowcount
        
        if deleted_counts['point_history'] > 0:
            print(f"  Deleted {deleted_counts['point_history']} point history entries")
        
        conn.commit()
        conn.close()
        
        print("\nSUCCESS: Cleanup complete!")
        print(f"\nSummary:")
        print(f"  - Scans deleted: {deleted_counts['scans']}")
        print(f"  - Scan points deleted: {deleted_counts['scan_points']}")
        print(f"  - Point history deleted: {deleted_counts['point_history']}")
        print(f"  - Competitor snapshots deleted: {deleted_counts['competitor_snapshots']}")
        print(f"  - Competitor history deleted: {deleted_counts['competitor_history']}")
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"\nERROR: Error cleaning up dummy data: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    print("=" * 60)
    print("Dummy Data Cleanup Script")
    print("=" * 60)
    print("\nThis will remove all dummy/test data from the database.")
    print("Known dummy patterns:")
    print("  - Keywords: 'pizza delivery', 'italian restaurant', 'food near me'")
    print("  - Business names: 'My Business', 'My Business Inc', 'My Business LLC'")
    print()
    
    # Skip confirmation if --yes flag is provided
    if '--yes' not in sys.argv:
        try:
            response = input("Continue? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cancelled.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)
    
    cleanup_dummy_data()
