#!/usr/bin/env python3
"""
Backfill script to extract local pack ranks from existing cache files
and update the database with the correct values.

This script:
1. Finds all point_history records with NULL local_pack_rank
2. Reconstructs the API payload that would have been used
3. Finds the corresponding cache file
4. Extracts places/local pack data from cache
5. Finds the business in the results
6. Updates the database with the correct local_pack_rank
"""

import sqlite3
import json
import hashlib
import os
from dotenv import load_dotenv

load_dotenv()

DB_NAME = 'scans.db'
CACHE_DIR = 'cache'
SERPER_API_URL = 'https://google.serper.dev'

def find_business_in_local_pack(local_pack, business_names):
    """
    Find business in local pack results (tries all business name variations)
    For places API results, uses array index (1-based) since position field may be uniform (all 1)
    Returns: (rank (1-based), matched_business_name) or (None, None) if not found
    """
    if not local_pack or not business_names:
        return None, None

    business_names_lower = [name.lower() for name in business_names]

    # Check if this is a places API result (all positions are 1)
    # If so, use array index for ranking instead of position field
    all_positions_one = all(result.get('position') == 1 for result in local_pack if result.get('position') is not None)
    use_array_index = all_positions_one and len(local_pack) > 1

    for idx, result in enumerate(local_pack, start=1):
        if use_array_index:
            # For places API with uniform positions, use array index
            position = idx
        else:
            # Use position field from API response if available, otherwise use enumerate index
            position = result.get('position')
            if position is None:
                position = idx

        title = result.get('title', '').lower() or result.get('name', '').lower()
        address = result.get('address', '').lower()

        # Check if any business name variation appears
        for i, biz_name_lower in enumerate(business_names_lower):
            if biz_name_lower in title or biz_name_lower in address:
                return position, business_names[i]  # Return original case

    return None, None

def get_cache_file_path(payload):
    """Get cache file path for a given payload"""
    payload_str = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.md5(payload_str.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f'{payload_hash}.json')

def load_cache_file(cache_path):
    """Load cache file and return the data (handling error responses)"""
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
        
        # Check if cached data includes status code (for error responses)
        if isinstance(cached_data, dict) and '_cached_status' in cached_data:
            status_code = cached_data['_cached_status']
            if status_code >= 400:
                return None  # Skip error responses
            return cached_data.get('data', cached_data)
        
        return cached_data
    except Exception as e:
        print(f"  Error loading cache file {cache_path}: {str(e)}")
        return None

def extract_local_pack_from_cache(cache_data):
    """Extract local pack/places data from cache file"""
    if not isinstance(cache_data, dict):
        return []
    
    # Handle 'places' from /places endpoint, or 'localPack'/'localPackResults' from /search endpoint
    local_pack = cache_data.get('places', []) or cache_data.get('localPack', []) or cache_data.get('localPackResults', [])
    
    if isinstance(local_pack, list):
        return local_pack
    return []

def backfill_local_pack_ranks():
    """Main backfill function"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    print("=" * 60)
    print("Local Pack Rank Backfill Script")
    print("=" * 60)
    
    # Get all records with NULL local_pack_rank
    c.execute('''
        SELECT ph.id, ph.project_id, ph.lat, ph.lon, ph.keyword, ph.business_name, ph.scan_date
        FROM point_history ph
        WHERE ph.local_pack_rank IS NULL
        ORDER BY ph.scan_date DESC
    ''')
    
    records = c.fetchall()
    total_records = len(records)
    
    if total_records == 0:
        print("\n[OK] No records with NULL local_pack_rank found!")
        conn.close()
        return
    
    print(f"\nFound {total_records} records with NULL local_pack_rank")
    print("Processing...\n")
    
    updated_count = 0
    not_found_count = 0
    cache_miss_count = 0
    error_count = 0
    
    # Process in batches for progress reporting
    for idx, record in enumerate(records, 1):
        record_id, project_id, lat, lon, keyword, business_name, scan_date = record
        
        try:
            # Get business names from project
            c.execute('SELECT business_names FROM projects WHERE id = ?', (project_id,))
            project_row = c.fetchone()
            
            if not project_row or not project_row[0]:
                # Fallback: use business_name from point_history
                business_names = [business_name] if business_name else []
            else:
                try:
                    business_names = json.loads(project_row[0])
                    if not business_names:
                        business_names = [business_name] if business_name else []
                except:
                    business_names = [business_name] if business_name else []
            
            if not business_names:
                print(f"  [{idx}/{total_records}] Record {record_id}: No business names, skipping")
                error_count += 1
                continue
            
            # Reconstruct payload for /places endpoint (as used in check_rankings_deep)
            primary_business_name = business_names[0]
            # Use keyword-only query to get full competitive local pack results
            query = keyword
            
            # Try /places endpoint first (has all 30 positions)
            payload_places = {
                'q': query,
                'location': f"{lat},{lon}",
                'gl': 'it',
                'hl': 'it'
            }
            
            cache_path = get_cache_file_path(payload_places)
            cache_data = load_cache_file(cache_path)
            
            # If /places cache not found, try /search endpoint (might have top 3)
            if cache_data is None:
                payload_search = {
                    'q': query,
                    'location': f"{lat},{lon}",
                    'gl': 'it',
                    'hl': 'it',
                    'num': 30
                }
                cache_path = get_cache_file_path(payload_search)
                cache_data = load_cache_file(cache_path)
            
            if cache_data is None:
                cache_miss_count += 1
                if idx % 100 == 0:
                    print(f"  [{idx}/{total_records}] Processed... (cache misses: {cache_miss_count})")
                continue
            
            # Extract places/local pack data
            local_pack = extract_local_pack_from_cache(cache_data)
            
            if not local_pack:
                not_found_count += 1
                if idx % 100 == 0:
                    print(f"  [{idx}/{total_records}] Processed... (no local pack data: {not_found_count})")
                continue
            
            # Find business in local pack
            # Check all results (1-30), not just top 3
            local_pack_all = local_pack[:30] if len(local_pack) > 30 else local_pack
            
            # First check top 3
            local_pack_top3 = local_pack_all[:3] if len(local_pack_all) > 3 else local_pack_all
            rank, matched_name = find_business_in_local_pack(local_pack_top3, business_names)
            
            # If not in top 3, check positions 4-30
            if rank is None and len(local_pack_all) > 3:
                local_pack_deep = local_pack_all[3:]
                deep_rank, matched_name = find_business_in_local_pack(local_pack_deep, business_names)
                if deep_rank:
                    rank = deep_rank + 3  # Add 3 since we're checking positions 4-30
            
            # Update database if rank found
            if rank is not None:
                # Update local_pack_rank
                c.execute('''
                    UPDATE point_history
                    SET local_pack_rank = ?
                    WHERE id = ?
                ''', (rank, record_id))
                
                # Also update display_rank if it's currently NULL or if local pack rank is better
                c.execute('''
                    SELECT organic_rank FROM point_history WHERE id = ?
                ''', (record_id,))
                organic_row = c.fetchone()
                organic_rank = organic_row[0] if organic_row else None
                
                # Display rank should be local pack rank if available, otherwise organic
                display_rank = rank if rank else organic_rank
                
                c.execute('''
                    UPDATE point_history
                    SET display_rank = ?
                    WHERE id = ?
                ''', (display_rank, record_id))
                
                updated_count += 1
                
                if idx % 50 == 0:
                    print(f"  [{idx}/{total_records}] Updated {updated_count} records...")
            else:
                not_found_count += 1
                if idx % 100 == 0:
                    print(f"  [{idx}/{total_records}] Processed... (not found: {not_found_count})")
        
        except Exception as e:
            error_count += 1
            print(f"  [{idx}/{total_records}] Error processing record {record_id}: {str(e)}")
            continue
    
    # Commit all changes
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 60)
    print("Backfill Complete!")
    print("=" * 60)
    print(f"Total records processed: {total_records}")
    print(f"  [OK] Updated with local pack rank: {updated_count}")
    print(f"  - Not found in local pack: {not_found_count}")
    print(f"  - Cache file missing: {cache_miss_count}")
    print(f"  ✗ Errors: {error_count}")
    print()

if __name__ == '__main__':
    import sys
    
    print("\nThis script will update local_pack_rank values in the database")
    print("by reprocessing existing cache files.\n")
    
    if '--yes' not in sys.argv:
        try:
            response = input("Continue? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cancelled.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)
    
    backfill_local_pack_ranks()
