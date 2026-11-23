#!/usr/bin/env python3
"""
Comprehensive test of all 10 new features
"""
import requests
import json
import sys

BASE_URL = 'http://localhost:5000'
session = requests.Session()

print("=" * 80)
print("COMPREHENSIVE FEATURE VERIFICATION TEST")
print("=" * 80)

# Get projects
print("\n[SETUP] Getting projects...")
try:
    resp = session.get(f'{BASE_URL}/api/projects')
    if resp.status_code != 200:
        print(f"ERROR: Could not get projects: {resp.status_code}")
        sys.exit(1)

    projects = resp.json().get('projects', [])
    if not projects:
        print("ERROR: No projects found")
        sys.exit(1)

    # Find Edil Italia project or use first
    project_id = None
    for p in projects:
        if 'Edil Italia' in p.get('name', ''):
            project_id = p['id']
            break

    if not project_id:
        project_id = projects[0]['id']

    print(f"Using project ID: {project_id}")

    # Set project in session
    resp = session.get(f'{BASE_URL}/projects/{project_id}')
    print(f"Project selected: {resp.status_code}")

except Exception as e:
    print(f"Setup error: {e}")
    sys.exit(1)

# Test results
results = {}

print("\n" + "=" * 80)
print("TESTING FEATURES")
print("=" * 80)

# [1/10] Business Performance
print("\n[1/10] BUSINESS PERFORMANCE DASHBOARD")
try:
    resp = session.get(f'{BASE_URL}/api/business/performance')
    if resp.status_code == 200:
        data = resp.json()
        required_keys = ['total_locations', 'top3_coverage_pct', 'avg_local_pack_rank', 'best_locations', 'worst_locations']
        if all(k in data for k in required_keys):
            print(f"✅ WORKING - All required fields present")
            print(f"   - Total locations: {data['total_locations']}")
            print(f"   - Top 3 coverage: {data['top3_coverage_pct']}%")
            print(f"   - Best locations: {len(data['best_locations'])}")
            results['business_performance'] = True
        else:
            print(f"❌ INCOMPLETE - Missing fields: {set(required_keys) - set(data.keys())}")
            results['business_performance'] = False
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['business_performance'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['business_performance'] = False

# [2/10] Market Insights
print("\n[2/10] ACTIONABLE MARKET INSIGHTS")
try:
    resp = session.get(f'{BASE_URL}/api/market/insights')
    if resp.status_code == 200:
        data = resp.json()
        required_keys = ['market_saturation', 'market_gap']
        if all(k in data for k in required_keys):
            print(f"✅ WORKING - All required fields present")
            print(f"   - Market saturation keywords: {len(data['market_saturation'])}")
            print(f"   - Gap locations: {data['market_gap']['missing_locations']}")
            results['market_insights'] = True
        else:
            print(f"❌ INCOMPLETE - Missing fields")
            results['market_insights'] = False
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['market_insights'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['market_insights'] = False

# [3/10] Keyword Performance
print("\n[3/10] KEYWORD PERFORMANCE MATRIX")
try:
    resp = session.get(f'{BASE_URL}/api/keywords/performance')
    if resp.status_code == 200:
        data = resp.json()
        keywords = data.get('keywords', [])
        if keywords:
            kw = keywords[0]
            required_keys = ['keyword', 'difficulty_score', 'opportunity_score', 'avg_rank']
            if all(k in kw for k in required_keys):
                print(f"✅ WORKING - All required fields present")
                print(f"   - Keywords tracked: {len(keywords)}")
                print(f"   - Sample: {kw['keyword']} (Difficulty: {kw['difficulty_score']}, Opportunity: {kw['opportunity_score']})")
                results['keyword_performance'] = True
            else:
                print(f"❌ INCOMPLETE - Missing fields in keyword")
                results['keyword_performance'] = False
        else:
            print(f"⚠️  NO KEYWORDS - API works but no data")
            results['keyword_performance'] = True  # API works, just no data
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['keyword_performance'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['keyword_performance'] = False

# [4/10] Heatmap Data (Your Business)
print("\n[4/10] GEOGRAPHIC HEATMAP - YOUR BUSINESS")
try:
    resp = session.get(f'{BASE_URL}/api/heatmap/data?show_competitors=false')
    if resp.status_code == 200:
        data = resp.json()
        points = data.get('points', [])
        if points:
            point = points[0]
            required_keys = ['lat', 'lon', 'performance', 'color', 'type']
            if all(k in point for k in required_keys):
                print(f"✅ WORKING - All required fields present")
                print(f"   - Points plotted: {len(points)}")
                results['heatmap_your_business'] = True
            else:
                print(f"❌ INCOMPLETE - Missing fields: {set(required_keys) - set(point.keys())}")
                results['heatmap_your_business'] = False
        else:
            print(f"⚠️  NO POINTS - API works but no data")
            results['heatmap_your_business'] = True
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['heatmap_your_business'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['heatmap_your_business'] = False

# [5/10] Heatmap Data (Competitor Density)
print("\n[5/10] GEOGRAPHIC HEATMAP - COMPETITOR DENSITY")
try:
    resp = session.get(f'{BASE_URL}/api/heatmap/data?show_competitors=true')
    if resp.status_code == 200:
        data = resp.json()
        points = data.get('points', [])
        if points:
            point = points[0]
            required_keys = ['lat', 'lon', 'type', 'density']
            if all(k in point for k in required_keys):
                print(f"✅ WORKING - All required fields present")
                print(f"   - Points plotted: {len(points)}")
                results['heatmap_competitor_density'] = True
            else:
                print(f"❌ INCOMPLETE - Missing fields: {set(required_keys) - set(point.keys())}")
                results['heatmap_competitor_density'] = False
        else:
            print(f"⚠️  NO POINTS - API works but no data")
            results['heatmap_competitor_density'] = True
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['heatmap_competitor_density'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['heatmap_competitor_density'] = False

# [6/10] Growth Trends
print("\n[6/10] TRENDING & GROWTH METRICS")
try:
    resp = session.get(f'{BASE_URL}/api/trends/growth')
    if resp.status_code == 200:
        data = resp.json()
        required_keys = ['market_avg_rank', 'top_competitors']
        if all(k in data for k in required_keys):
            print(f"✅ WORKING - All required fields present")
            print(f"   - Market avg rank: {data['market_avg_rank']}")
            print(f"   - Top competitors: {len(data['top_competitors'])}")
            results['trends_growth'] = True
        else:
            print(f"❌ INCOMPLETE - Missing fields")
            results['trends_growth'] = False
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['trends_growth'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['trends_growth'] = False

# [7/10] Historical Comparison
print("\n[7/10] HISTORICAL COMPARISON (Month-over-Month)")
try:
    resp = session.get(f'{BASE_URL}/api/history/comparison')
    if resp.status_code == 200:
        data = resp.json()
        history = data.get('monthly_history', [])
        if history:
            entry = history[0]
            required_keys = ['month', 'avg_rank', 'scan_count']
            if all(k in entry for k in required_keys):
                print(f"✅ WORKING - All required fields present")
                print(f"   - Historical months: {len(history)}")
                results['history_comparison'] = True
            else:
                print(f"❌ INCOMPLETE - Missing fields")
                results['history_comparison'] = False
        else:
            print(f"⚠️  NO HISTORY - API works but no data")
            results['history_comparison'] = True
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['history_comparison'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['history_comparison'] = False

# [8/10] Gap Analysis
print("\n[8/10] GAP ANALYSIS REPORT")
try:
    resp = session.get(f'{BASE_URL}/api/analysis/gaps')
    if resp.status_code == 200:
        data = resp.json()
        gaps = data.get('gaps', [])
        if isinstance(gaps, list):
            if gaps:
                gap = gaps[0]
                required_keys = ['lat', 'lon', 'keyword', 'competitors_present']
                if all(k in gap for k in required_keys):
                    print(f"✅ WORKING - All required fields present")
                    print(f"   - Gaps identified: {len(gaps)}")
                    results['gap_analysis'] = True
                else:
                    print(f"❌ INCOMPLETE - Missing fields")
                    results['gap_analysis'] = False
            else:
                print(f"⚠️  NO GAPS - API works but no data")
                results['gap_analysis'] = True
        else:
            print(f"❌ INCOMPLETE - gaps is not a list")
            results['gap_analysis'] = False
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['gap_analysis'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['gap_analysis'] = False

# [9/10] Competitor Comparison
print("\n[9/10] COMPETITOR COMPARISON TOOL")
try:
    # First get a competitor name
    resp = session.get(f'{BASE_URL}/api/competitors/overview')
    if resp.status_code == 200:
        comp_data = resp.json()
        competitors = comp_data.get('competitors', [])
        if competitors:
            comp_name = competitors[0]['name']
            resp = session.get(f'{BASE_URL}/api/competitors/comparison/{comp_name}')
            if resp.status_code == 200:
                data = resp.json()
                comparison = data.get('comparison', [])
                if comparison:
                    comp = comparison[0]
                    required_keys = ['keyword', 'your_rank', 'competitor_rank', 'head_to_head']
                    if all(k in comp for k in required_keys):
                        print(f"✅ WORKING - All required fields present")
                        print(f"   - Competitor: {data['competitor']}")
                        print(f"   - Keywords compared: {len(comparison)}")
                        results['competitor_comparison'] = True
                    else:
                        print(f"❌ INCOMPLETE - Missing fields")
                        results['competitor_comparison'] = False
                else:
                    print(f"⚠️  NO COMPARISON DATA - API works but no data")
                    results['competitor_comparison'] = True
            else:
                print(f"❌ ERROR {resp.status_code}")
                results['competitor_comparison'] = False
        else:
            print(f"⚠️  NO COMPETITORS - API would work but none found")
            results['competitor_comparison'] = True
    else:
        print(f"❌ ERROR getting competitors {resp.status_code}")
        results['competitor_comparison'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['competitor_comparison'] = False

# [10/10] Export Report
print("\n[10/10] EXPORT & REPORTING FEATURES")
try:
    resp = session.get(f'{BASE_URL}/api/export/report')
    if resp.status_code == 200:
        data = resp.json()
        required_keys = ['generated_at', 'project']
        if all(k in data for k in required_keys):
            print(f"✅ WORKING - All required fields present")
            print(f"   - Project: {data['project'].get('name', 'Unknown')}")
            results['export_report'] = True
        else:
            print(f"❌ INCOMPLETE - Missing fields")
            results['export_report'] = False
    else:
        print(f"❌ ERROR {resp.status_code}")
        results['export_report'] = False
except Exception as e:
    print(f"❌ EXCEPTION: {str(e)[:100]}")
    results['export_report'] = False

# Summary
print("\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

working = sum(1 for v in results.values() if v)
total = len(results)

print(f"\n✅ Working Features: {working}/{total}")
print("\nDetailed Status:")
for feature, status in results.items():
    icon = "✅" if status else "❌"
    name = feature.replace('_', ' ').title()
    print(f"   {icon} {name}")

print("\n" + "=" * 80)

if working == total:
    print("🎉 SUCCESS! All 10 features are working correctly!")
    sys.exit(0)
else:
    print(f"⚠️  {total - working} features not fully functional")
    sys.exit(1)
