#!/usr/bin/env python3
"""
Script to remove all data before 19/01 (January 19th).
This will remove data from:
- scans table (date field)
- point_history table (scan_date field)
- competitor_history table (scan_date field)
- scan_points table (via foreign key relationships)
- competitor_snapshots table (via foreign key relationships)
"""

import sqlite3
from datetime import datetime
import sys

DB_NAME = 'scans.db'
CUTOFF_DATE = '2026-01-19'  # January 19th, 2026

def check_dates():
    """Check what date ranges exist in the database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    print("Checking date ranges in database...")
    
    # Check scans table
    c.execute('SELECT MIN(date), MAX(date), COUNT(*) FROM scans')
    result = c.fetchone()
    if result[0]:
        print(f"\nscans table:")
        print(f"  Min date: {result[0]}")
        print(f"  Max date: {result[1]}")
        print(f"  Total records: {result[2]}")
        c.execute('SELECT COUNT(*) FROM scans WHERE date < ?', (CUTOFF_DATE,))
        count = c.fetchone()[0]
        print(f"  Records before {CUTOFF_DATE}: {count}")
    
    # Check point_history table
    c.execute('SELECT MIN(scan_date), MAX(scan_date), COUNT(*) FROM point_history')
    result = c.fetchone()
    if result[0]:
        print(f"\npoint_history table:")
        print(f"  Min date: {result[0]}")
        print(f"  Max date: {result[1]}")
        print(f"  Total records: {result[2]}")
        c.execute('SELECT COUNT(*) FROM point_history WHERE scan_date < ?', (CUTOFF_DATE,))
        count = c.fetchone()[0]
        print(f"  Records before {CUTOFF_DATE}: {count}")
    
    # Check competitor_history table
    c.execute('SELECT MIN(scan_date), MAX(scan_date), COUNT(*) FROM competitor_history')
    result = c.fetchone()
    if result[0]:
        print(f"\ncompetitor_history table:")
        print(f"  Min date: {result[0]}")
        print(f"  Max date: {result[1]}")
        print(f"  Total records: {result[2]}")
        c.execute('SELECT COUNT(*) FROM competitor_history WHERE scan_date < ?', (CUTOFF_DATE,))
        count = c.fetchone()[0]
        print(f"  Records before {CUTOFF_DATE}: {count}")
    
    conn.close()

def remove_old_data():
    """Remove all data before the cutoff date"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    deleted_counts = {
        'scans': 0,
        'scan_points': 0,
        'point_history': 0,
        'competitor_history': 0,
        'competitor_snapshots': 0
    }
    
    try:
        print(f"\nRemoving all data before {CUTOFF_DATE}...")
        
        # First, find scan IDs that will be deleted
        c.execute('SELECT id FROM scans WHERE date < ?', (CUTOFF_DATE,))
        old_scan_ids = [row[0] for row in c.fetchall()]
        
        if old_scan_ids:
            print(f"Found {len(old_scan_ids)} scans to delete")
            
            # Delete competitor_snapshots for scan_points that belong to old scans
            c.execute('''
                DELETE FROM competitor_snapshots 
                WHERE scan_point_id IN (
                    SELECT id FROM scan_points WHERE scan_id IN ({})
                )
            '''.format(','.join(['?' for _ in old_scan_ids])), old_scan_ids)
            deleted_counts['competitor_snapshots'] = c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} competitor snapshots")
            
            # Delete competitor_history for scan_points that belong to old scans
            c.execute('''
                DELETE FROM competitor_history 
                WHERE scan_point_id IN (
                    SELECT id FROM scan_points WHERE scan_id IN ({})
                )
            '''.format(','.join(['?' for _ in old_scan_ids])), old_scan_ids)
            deleted_counts['competitor_history'] += c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} competitor history entries (via scan_points)")
            
            # Delete scan_points for old scans
            c.execute('DELETE FROM scan_points WHERE scan_id IN ({})'.format(','.join(['?' for _ in old_scan_ids])), old_scan_ids)
            deleted_counts['scan_points'] = c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} scan points")
            
            # Delete old scans
            c.execute('DELETE FROM scans WHERE id IN ({})'.format(','.join(['?' for _ in old_scan_ids])), old_scan_ids)
            deleted_counts['scans'] = c.rowcount
            if c.rowcount > 0:
                print(f"  Deleted {c.rowcount} scans")
        
        # Delete point_history entries with old scan_date
        c.execute('DELETE FROM point_history WHERE scan_date < ?', (CUTOFF_DATE,))
        deleted_counts['point_history'] = c.rowcount
        if c.rowcount > 0:
            print(f"  Deleted {c.rowcount} point history entries")
        
        # Delete competitor_history entries with old scan_date (that weren't deleted via scan_points)
        c.execute('DELETE FROM competitor_history WHERE scan_date < ?', (CUTOFF_DATE,))
        deleted_counts['competitor_history'] += c.rowcount
        if c.rowcount > 0:
            print(f"  Deleted {c.rowcount} additional competitor history entries")
        
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
        print(f"\nERROR: Error removing old data: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    print("=" * 60)
    print("Remove Old Data Script")
    print("=" * 60)
    print(f"\nThis will remove all data before {CUTOFF_DATE} (January 19th, 2026).")
    print()
    
    # First check what will be deleted
    check_dates()
    
    # Skip confirmation if --yes flag is provided
    if '--yes' not in sys.argv:
        try:
            response = input("\nContinue? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cancelled.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)
    
    remove_old_data()
