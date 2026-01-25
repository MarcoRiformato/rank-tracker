# Cleanup Scripts Consolidation

## Status: ARCHIVED

The following standalone cleanup scripts have been consolidated into `admin_cleanup.py`:

- `cleanup_dummy_data.py` - Remove fake competitor data
- `remove_old_data.py` - Remove old scan records
- `remove_pizza_keyword.py` - Specific data cleanup (archived)
- `check_db_data.py` - Database statistics
- `check_scan_cities.py` - City data analysis
- `check_parabiago.py` - Location-specific cleanup
- `check_mismatch.py` - Data consistency checking
- `inspect_rogue_data.py` - Find anomalous data
- `analyze_cache.py` - Cache analysis

## Why Consolidate?

These scripts indicate **underlying data quality issues** that require system fixes rather than frequent manual cleanup. The report analysis found:

1. **Silent failures in competitor saves** → Fixed with proper error handling
2. **Dummy mode pollution** → Fixed by ensuring USE_DUMMY_MODE=false
3. **Hardcoded landing pages** → Disabled until per-project configuration added
4. **Wrong cache data** → Cleared and system fixed to prevent reoccurrence

## New Usage

Use the consolidated admin tool:

```bash
# Check database integrity
python admin_cleanup.py --check

# Remove dummy data (if needed)
python admin_cleanup.py --cleanup-dummy

# Remove old scans
python admin_cleanup.py --remove-old-data 30

# Analyze cache
python admin_cleanup.py --analyze-cache

# All non-destructive checks
python admin_cleanup.py --all

# DANGEROUS: Wipe all scan results
python admin_cleanup.py --wipe-results
```

## Next Steps

These operations should eventually be:
1. **Removed** once system is fully stable
2. **Integrated into admin dashboard** for non-technical users
3. **Automated** with cleanup job schedules

For now, use `admin_cleanup.py` as the primary tool for database maintenance.
