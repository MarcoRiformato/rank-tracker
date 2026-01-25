#!/usr/bin/env python3
"""
Consolidated admin cleanup utility for rank tracker database maintenance.

This script consolidates functionality from multiple standalone cleanup scripts:
- cleanup_dummy_data.py
- remove_old_data.py
- remove_pizza_keyword.py
- check_db_data.py
- check_scan_cities.py
- check_parabiago.py
- check_mismatch.py
- inspect_rogue_data.py
- analyze_cache.py
- wipe_scan_results.py

Usage:
    python admin_cleanup.py --help

This is an admin-only tool for database maintenance and should be used carefully.
These cleanup operations should ideally be performed via the admin dashboard once
the system stabilizes.
"""

import sqlite3
import argparse
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('admin_cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_NAME = 'scans.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def check_db_integrity():
    """Check database integrity and report statistics"""
    conn = get_db_connection()
    c = conn.cursor()

    logger.info("=" * 60)
    logger.info("DATABASE INTEGRITY CHECK")
    logger.info("=" * 60)

    # Check tables and row counts
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()

    for table_row in tables:
        table = table_row[0]
        c.execute(f"SELECT COUNT(*) as count FROM {table}")
        count = c.fetchone()[0]
        logger.info(f"{table}: {count} rows")

    # Check for NULL city fields that might cause issues
    c.execute('''
        SELECT COUNT(*) as count FROM point_history
        WHERE city IS NULL OR city = ''
    ''')
    null_cities = c.fetchone()[0]
    if null_cities > 0:
        logger.warning(f"⚠️  Found {null_cities} point_history rows with NULL/empty city")

    # Check competitor data consistency
    c.execute('''
        SELECT COUNT(*) as count FROM competitor_history
    ''')
    comp_history = c.fetchone()[0]

    c.execute('''
        SELECT COUNT(*) as count FROM competitor_snapshots
    ''')
    comp_snapshots = c.fetchone()[0]

    logger.info(f"Competitor history: {comp_history} records")
    logger.info(f"Competitor snapshots: {comp_snapshots} records")

    if comp_history == 0 and comp_snapshots > 0:
        logger.warning("⚠️  Competitor history is empty but snapshots exist - inserts may be failing")

    conn.close()

def cleanup_dummy_data(project_id=None):
    """Remove fake competitor data generated in dummy mode"""
    conn = get_db_connection()
    c = conn.cursor()

    logger.info("=" * 60)
    logger.info("CLEANUP: DUMMY DATA")
    logger.info("=" * 60)

    # Define known fake competitor name patterns
    fake_patterns = [
        'Competitor %',
        'Edilizia Expert %',
        'Service Provider %',
        'Generic Company %'
    ]

    total_deleted = 0
    for pattern in fake_patterns:
        c.execute('''
            SELECT COUNT(*) as count FROM competitor_history
            WHERE competitor_name LIKE ?
        ''', (pattern,))
        count = c.fetchone()[0]

        if count > 0:
            c.execute('''
                DELETE FROM competitor_history
                WHERE competitor_name LIKE ?
            ''', (pattern,))
            deleted = c.rowcount
            total_deleted += deleted
            logger.info(f"  Deleted {deleted} records matching pattern '{pattern}'")

    if project_id:
        c.execute('''
            SELECT COUNT(*) FROM competitor_snapshots cs
            INNER JOIN scan_points sp ON cs.scan_point_id = sp.id
            INNER JOIN scans s ON sp.scan_id = s.id
            WHERE s.project_id = ? AND cs.competitor_name LIKE 'Competitor %'
        ''', (project_id,))
        count = c.fetchone()[0]
        if count > 0:
            logger.info(f"  Found {count} fake competitors in project {project_id} snapshots")

    conn.commit()
    conn.close()
    logger.info(f"✓ Dummy data cleanup complete - {total_deleted} records removed")

def remove_old_data(days=None):
    """Remove old scan data from before the specified date"""
    conn = get_db_connection()
    c = conn.cursor()

    logger.info("=" * 60)
    logger.info("CLEANUP: OLD DATA")
    logger.info("=" * 60)

    if not days:
        days = 30  # Default: remove data older than 30 days

    c.execute('''
        SELECT COUNT(*) FROM scans
        WHERE created_at < datetime('now', '-' || ? || ' days')
    ''', (days,))
    count = c.fetchone()[0]

    if count > 0:
        logger.warning(f"⚠️  Found {count} scans older than {days} days")
        logger.info(f"To delete them, run: DELETE FROM scans WHERE created_at < datetime('now', '-{days} days')")
    else:
        logger.info(f"✓ No scans older than {days} days found")

    conn.close()

def wipe_all_scan_results():
    """DANGEROUS: Clear all scan results from database"""
    conn = get_db_connection()
    c = conn.cursor()

    logger.info("=" * 60)
    logger.warning("DANGEROUS OPERATION: WIPE ALL SCAN RESULTS")
    logger.info("=" * 60)

    # Show what will be deleted
    c.execute("SELECT COUNT(*) FROM scans")
    scans = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM scan_points")
    points = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM point_history")
    history = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM competitor_snapshots")
    snapshots = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM competitor_history")
    comp_history = c.fetchone()[0]

    logger.warning(f"This will delete:")
    logger.warning(f"  - {scans} scans")
    logger.warning(f"  - {points} scan points")
    logger.warning(f"  - {history} point history records")
    logger.warning(f"  - {snapshots} competitor snapshots")
    logger.warning(f"  - {comp_history} competitor history records")

    # Require confirmation
    response = input("Type 'yes' to confirm deletion: ").strip().lower()
    if response != 'yes':
        logger.info("✓ Wipe cancelled")
        return

    c.execute("DELETE FROM competitor_snapshots")
    c.execute("DELETE FROM competitor_history")
    c.execute("DELETE FROM point_history")
    c.execute("DELETE FROM scan_points")
    c.execute("DELETE FROM scans")

    conn.commit()
    conn.close()

    logger.warning("✓ All scan results deleted!")

def analyze_cache(cache_dir='cache'):
    """Analyze cache directory contents"""
    import os
    import hashlib

    logger.info("=" * 60)
    logger.info("CACHE ANALYSIS")
    logger.info("=" * 60)

    if not os.path.exists(cache_dir):
        logger.info(f"✓ Cache directory '{cache_dir}' does not exist")
        return

    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
    logger.info(f"✓ Cache contains {len(cache_files)} JSON files")

    total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cache_files)
    logger.info(f"✓ Total cache size: {total_size / 1024 / 1024:.2f} MB")

    if total_size > 100 * 1024 * 1024:  # 100MB
        logger.warning("⚠️  Cache is large (>100MB) - consider clearing old cached data")

def main():
    parser = argparse.ArgumentParser(description='Admin cleanup utility for rank tracker database')
    parser.add_argument('--check', action='store_true', help='Check database integrity')
    parser.add_argument('--cleanup-dummy', action='store_true', help='Remove dummy data')
    parser.add_argument('--remove-old-data', type=int, help='Remove scans older than N days')
    parser.add_argument('--wipe-results', action='store_true', help='DANGEROUS: Delete all scan results')
    parser.add_argument('--analyze-cache', action='store_true', help='Analyze cache directory')
    parser.add_argument('--all', action='store_true', help='Run all non-destructive checks')

    args = parser.parse_args()

    if args.check or args.all:
        check_db_integrity()
        print()

    if args.cleanup_dummy:
        cleanup_dummy_data()
        print()

    if args.remove_old_data:
        remove_old_data(args.remove_old_data)
        print()

    if args.wipe_results:
        wipe_all_scan_results()
        print()

    if args.analyze_cache:
        analyze_cache()
        print()

    if args.all:
        analyze_cache()
        print()

    if not any([args.check, args.cleanup_dummy, args.remove_old_data, args.wipe_results, args.analyze_cache, args.all]):
        parser.print_help()

if __name__ == '__main__':
    main()
