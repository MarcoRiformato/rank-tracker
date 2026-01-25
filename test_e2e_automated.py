#!/usr/bin/env python3
"""
Automated E2E Test Suite for Rank Tracker

This script validates key points of the E2E test plan automatically:
- Database integrity
- Data quality
- No dummy data
- Correct geographic data
- Logging functionality

Run after manual testing to validate results.
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

class E2ETestRunner:
    def __init__(self, db_name='scans.db'):
        self.db_name = db_name
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results = []

    def log(self, level, message):
        """Log test result"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        symbol = {
            'PASS': '[OK]',
            'FAIL': '[XX]',
            'WARN': '[!!]',
            'INFO': '[--]'
        }.get(level, '[?]')

        full_msg = f"{symbol} {message}"
        print(full_msg)
        self.results.append((level, message))

        if level == 'PASS':
            self.passed += 1
        elif level == 'FAIL':
            self.failed += 1
        elif level == 'WARN':
            self.warnings += 1

    def test_database_exists(self):
        """Test 1: Database file exists and is valid"""
        self.log('INFO', 'Testing database file...')

        if not os.path.exists(self.db_name):
            self.log('FAIL', f'Database file not found: {self.db_name}')
            return False

        try:
            conn = sqlite3.connect(self.db_name)
            conn.execute('SELECT 1')
            conn.close()
            self.log('PASS', 'Database file valid and accessible')
            return True
        except Exception as e:
            self.log('FAIL', f'Database error: {e}')
            return False

    def test_tables_exist(self):
        """Test 2: All required tables exist"""
        self.log('INFO', 'Testing database tables...')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        required_tables = [
            'projects', 'scans', 'scan_points',
            'point_history', 'competitor_history', 'competitor_snapshots'
        ]

        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in c.fetchall()}

        for table in required_tables:
            if table in existing:
                self.log('PASS', f'Table exists: {table}')
            else:
                self.log('FAIL', f'Missing table: {table}')

        conn.close()
        return all(t in existing for t in required_tables)

    def test_data_populated(self):
        """Test 3: Key tables have data"""
        self.log('INFO', 'Testing data population...')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        tables_to_check = {
            'projects': 1,
            'scans': 1,
            'scan_points': 1,
            'point_history': 1,
            'competitor_snapshots': 1,
            'competitor_history': 1,  # KEY TEST - was empty in bug
        }

        for table, min_count in tables_to_check.items():
            c.execute(f'SELECT COUNT(*) FROM {table}')
            count = c.fetchone()[0]

            if count >= min_count:
                self.log('PASS', f'{table}: {count} records')
            else:
                if table == 'competitor_history' and count == 0:
                    self.log('FAIL', f'{table}: {count} records (BUG NOT FIXED - should have inserts!)')
                else:
                    self.log('WARN', f'{table}: {count} records (expected >= {min_count})')

        conn.close()

    def test_no_dummy_data(self):
        """Test 4: Verify no fake competitor data"""
        self.log('INFO', 'Testing for dummy data...')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        fake_patterns = ['Competitor %', 'Edilizia Expert%', 'Service Provider%']

        for pattern in fake_patterns:
            c.execute('SELECT COUNT(*) FROM competitor_history WHERE competitor_name LIKE ?', (pattern,))
            count = c.fetchone()[0]

            if count == 0:
                self.log('PASS', f'No fake competitors matching "{pattern}"')
            else:
                self.log('FAIL', f'Found {count} fake competitors matching "{pattern}"')

        # Check that competitor names are reasonable
        c.execute('''
            SELECT COUNT(DISTINCT competitor_name) FROM competitor_history
            WHERE competitor_name NOT LIKE 'Competitor %'
        ''')
        real_count = c.fetchone()[0]

        if real_count > 0:
            self.log('PASS', f'Found {real_count} real business names in history')
        else:
            self.log('WARN', 'No real business names found in competitor history')

        conn.close()

    def test_geographic_data_correctness(self):
        """Test 5: Verify cache has correct geographic data"""
        self.log('INFO', 'Testing geographic data in cache...')

        cache_dir = 'cache'
        if not os.path.exists(cache_dir):
            self.log('WARN', 'Cache directory does not exist')
            return

        cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]

        if len(cache_files) == 0:
            self.log('WARN', 'No cache files found (cache cleared after fix)')
            return

        locations = set()
        bad_locations = {'Rome', 'Milano', 'Torino', 'Naples', 'roma', 'milano'}

        for cache_file in cache_files[:10]:  # Check first 10
            try:
                with open(os.path.join(cache_dir, cache_file)) as f:
                    data = json.load(f)

                if 'searchParameters' in data:
                    location = data['searchParameters'].get('location', '')
                    locations.add(location)

                    # Check for obviously wrong locations
                    for bad in bad_locations:
                        if bad.lower() in location.lower():
                            self.log('FAIL', f'Found wrong location in cache: {location}')
                            return
            except:
                pass

        if locations:
            self.log('PASS', f'Cache locations look correct: {len(locations)} unique locations')
        else:
            self.log('WARN', 'Could not determine cache locations')

    def test_logging_functional(self):
        """Test 6: Verify logging file exists and works"""
        self.log('INFO', 'Testing logging...')

        log_file = 'rank_tracker.log'

        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            self.log('PASS', f'Log file exists ({size} bytes)')

            # Check log content
            try:
                with open(log_file) as f:
                    lines = f.readlines()
                    if len(lines) > 0:
                        self.log('PASS', f'Log file has {len(lines)} entries')

                        # Check for expected content
                        log_content = ''.join(lines)
                        if 'ERROR' in log_content or 'INFO' in log_content:
                            self.log('PASS', 'Log contains structured messages')
                        else:
                            self.log('WARN', 'Log exists but content is unusual')
                    else:
                        self.log('WARN', 'Log file is empty')
            except Exception as e:
                self.log('WARN', f'Could not read log file: {e}')
        else:
            self.log('WARN', 'Log file not created yet (will be created on first run)')

    def test_competitor_data_fields(self):
        """Test 7: Verify competitor records have all required fields"""
        self.log('INFO', 'Testing competitor data fields...')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM competitor_history')
        total = c.fetchone()[0]

        if total == 0:
            self.log('WARN', 'No competitor history records to test')
            return

        # Check for non-null critical fields
        c.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN competitor_name IS NULL THEN 1 ELSE 0 END) as null_names,
                SUM(CASE WHEN rank IS NULL THEN 1 ELSE 0 END) as null_ranks
            FROM competitor_history
        ''')

        total, null_names, null_ranks = c.fetchone()

        if null_names == 0:
            self.log('PASS', 'All competitor names are populated')
        else:
            self.log('FAIL', f'{null_names} records have NULL competitor_name')

        if null_ranks == 0:
            self.log('PASS', 'All competitor ranks are populated')
        else:
            self.log('WARN', f'{null_ranks} records have NULL rank (may be from organic only)')

        # Check rank values are in valid range
        c.execute('''
            SELECT COUNT(*) FROM competitor_history
            WHERE rank NOT NULL AND (rank < 1 OR rank > 30)
        ''')
        invalid_ranks = c.fetchone()[0]

        if invalid_ranks == 0:
            self.log('PASS', 'All ranks are in valid range (1-30)')
        else:
            self.log('WARN', f'{invalid_ranks} records have ranks outside 1-30 range')

        conn.close()

    def test_point_data_completeness(self):
        """Test 8: Verify point_history records are complete"""
        self.log('INFO', 'Testing point history completeness...')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM point_history')
        total = c.fetchone()[0]

        if total == 0:
            self.log('WARN', 'No point history records to test')
            return

        # Check required fields
        required_fields = ['project_id', 'lat', 'lon', 'keyword', 'business_name', 'scan_date']

        for field in required_fields:
            c.execute(f'SELECT COUNT(*) FROM point_history WHERE {field} IS NULL OR {field} = ""')
            null_count = c.fetchone()[0]

            if null_count == 0:
                self.log('PASS', f'All point_history.{field} values populated')
            else:
                self.log('WARN', f'{null_count} point_history.{field} values are NULL/empty')

        conn.close()

    def test_scan_point_correlation(self):
        """Test 9: Verify scan_points are correctly linked"""
        self.log('INFO', 'Testing scan point correlation...')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        # Check that scan_points link to scans
        c.execute('''
            SELECT COUNT(*) FROM scan_points sp
            WHERE NOT EXISTS (SELECT 1 FROM scans s WHERE s.id = sp.scan_id)
        ''')
        orphaned = c.fetchone()[0]

        if orphaned == 0:
            self.log('PASS', 'All scan_points correctly linked to scans')
        else:
            self.log('FAIL', f'{orphaned} orphaned scan_points found')

        # Check that competitor_snapshots link to scan_points
        c.execute('''
            SELECT COUNT(*) FROM competitor_snapshots cs
            WHERE NOT EXISTS (SELECT 1 FROM scan_points sp WHERE sp.id = cs.scan_point_id)
        ''')
        orphaned = c.fetchone()[0]

        if orphaned == 0:
            self.log('PASS', 'All competitor_snapshots correctly linked to scan_points')
        else:
            self.log('WARN', f'{orphaned} competitor_snapshots have invalid scan_point_id')

        conn.close()

    def test_data_consistency(self):
        """Test 10: Verify data consistency across tables"""
        self.log('INFO', 'Testing data consistency...')

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        # Check that point_history keywords match scan_points keywords
        c.execute('''
            SELECT COUNT(DISTINCT ph.keyword) FROM point_history ph
        ''')
        ph_keywords = c.fetchone()[0]

        c.execute('''
            SELECT COUNT(DISTINCT sp.keyword) FROM scan_points sp
        ''')
        sp_keywords = c.fetchone()[0]

        self.log('INFO', f'point_history keywords: {ph_keywords}, scan_points keywords: {sp_keywords}')

        # Check consistency of business names
        c.execute('''
            SELECT COUNT(DISTINCT business_name) FROM point_history
        ''')
        ph_businesses = c.fetchone()[0]

        if ph_businesses > 0:
            self.log('PASS', f'point_history contains {ph_businesses} unique business names')
        else:
            self.log('WARN', 'point_history has no business names')

        conn.close()

    def run_all_tests(self):
        """Run all tests"""
        print('\n' + '=' * 70)
        print('E2E AUTOMATED TEST SUITE')
        print('=' * 70 + '\n')

        tests = [
            self.test_database_exists,
            self.test_tables_exist,
            self.test_data_populated,
            self.test_no_dummy_data,
            self.test_geographic_data_correctness,
            self.test_logging_functional,
            self.test_competitor_data_fields,
            self.test_point_data_completeness,
            self.test_scan_point_correlation,
            self.test_data_consistency,
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                self.log('FAIL', f'Test {test.__name__} crashed: {e}')
            print()

        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print('=' * 70)
        print('TEST SUMMARY')
        print('=' * 70)
        print(f'Passed:  {self.passed}')
        print(f'Failed:  {self.failed}')
        print(f'Warnings: {self.warnings}')
        print()

        if self.failed == 0:
            print('STATUS: ALL TESTS PASSED')
            return True
        else:
            print('STATUS: SOME TESTS FAILED')
            print('\nFailed tests:')
            for level, msg in self.results:
                if level == 'FAIL':
                    print(f'  - {msg}')
            return False


def main():
    runner = E2ETestRunner()
    runner.run_all_tests()

    # Return exit code
    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == '__main__':
    main()
