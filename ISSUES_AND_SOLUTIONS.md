# Test Results Analysis & Solution Strategy

**Date**: 2026-01-24
**Status**: Data quality improvements needed before production

---

## Executive Summary

The core E2E tests passed ✅, but real-world data revealed several quality issues that should be addressed:

1. **Business name variations** - Need deduplication
2. **Geographic filtering** - Need to exclude out-of-area competitors
3. **Non-competitor results** - Need to filter listicles/directories
4. **Missing rich data** - Need local pack endpoint for ratings/reviews
5. **Business matching** - Need real test with your actual business

---

## Issue 1: Business Name Variations & Duplicates

### The Problem

Your business has multiple names:
- "Edil Italia di Sergio Fuscaldo"
- "Sergio Fuscaldo"
- "Edilitalia"

And in competitor data, we see:
- "Cla. Vi. Ristrutturazioni" (3 records)
- "CLA.VI. Ristrutturazioni | Saronno" (3 records)

Same company, different formatting = duplicate tracking

### Root Cause

Serper API returns titles exactly as they appear on Google:
- Different pages use different formatting
- No normalization in extraction logic

### Solutions

#### **Option A: Normalize in Extraction (RECOMMENDED)**
```python
def normalize_competitor_name(name):
    """
    Normalize competitor names for deduplication
    """
    if not name:
        return name

    # Remove extra spaces and special characters
    normalized = name.strip()
    normalized = normalized.upper()
    # Remove dots, pipes, dashes for comparison
    normalized = normalized.replace('.', '').replace('|', '').replace('-', ' ')
    # Keep only alphanumeric and spaces
    normalized = ''.join(c for c in normalized if c.isalnum() or c.isspace())
    return ' '.join(normalized.split())  # Remove extra spaces

# Before saving:
# "CLA.VI. Ristrutturazioni | Saronno"
# becomes "CLAVI RISTRUTTURAZIONI SARONNO"
```

**Pros**: Automatic, consistent, clean
**Cons**: Loses original formatting, need to store original separately

#### **Option B: Fuzzy Matching**
Use Levenshtein distance to detect similar names:
```python
from difflib import SequenceMatcher

def is_duplicate(name1, name2, threshold=0.85):
    """Check if two names are likely the same business"""
    ratio = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
    return ratio > threshold
```

**Pros**: Handles minor variations intelligently
**Cons**: More complex, needs tuning

#### **Option C: Manual Alias System (UI-Based)**
Allow users to mark competitors as duplicates:
```
UI shows: "These might be the same business"
User confirms or denies
System groups them together for reporting
```

**Pros**: Accurate, user-controlled
**Cons**: Manual work, slower

### Recommendation

**Combine A + C**:
1. Normalize names on save (Option A) to prevent most duplicates
2. Add UI feature for users to mark aliases (Option C) for edge cases
3. Store original name in separate field for reference

---

## Issue 2: Geographic Filtering - Competitors Outside Saronno

### The Problem

The data you showed includes:
- "R.A Edilizia: Ristrutturazione chiavi in mano a Varese" ← VARESE, not Saronno!

Your service area is Saronno, but competitors from other areas are being saved.

### Root Cause

API results don't have geographic data at extraction time:
- Organic search results don't include address/location
- Can't filter by location without additional API calls
- Currently saving all results regardless of location

### Solutions

#### **Option A: Use Local Pack Results (BEST)**
Local pack (Maps) results HAVE:
- Address field
- Latitude/longitude
- City information

Extract from `/places` endpoint instead of `/search`:
```python
if 'places' in response:
    for place in response['places']:
        address = place.get('address', '')
        # Filter: only keep if address contains "Saronno"
        if 'saronno' in address.lower():
            save_competitor(place)
```

**Pros**: Actual geographic data from Google Maps
**Cons**: Requires both endpoints, more data

#### **Option B: Post-Filter by Reverse Geocoding**
After getting rank, reverse geocode competitor address:
```python
address = reverse_geocode(competitor_lat, competitor_lon)
city = extract_city(address)
if city.lower() == 'saronno':
    save_competitor()
```

**Pros**: Works with current data
**Cons**: Extra API calls (slow, expensive)

#### **Option C: Keyword-Based Filtering**
Filter based on keywords in title:
```python
REGIONAL_INDICATORS = ['varese', 'milano', 'como', 'brescia']
for result in organic_results:
    title = result.get('title', '').lower()
    is_local = any(city in title for city in REGIONAL_INDICATORS)
    if not is_local:  # Only save if NOT from other regions
        save_competitor()
```

**Pros**: Simple, no extra calls
**Cons**: Imperfect (misses subtle references)

### Recommendation

**Use Option A** (Local Pack Results):
1. Modify `check_rankings_standard()` to call `/places` endpoint
2. Extract address from local pack
3. Filter: only save if address contains "Saronno"
4. This gives you ratings, reviews, address, etc. too!

---

## Issue 3: Filter Out Non-Competitor Results

### The Problem

"I 40 migliori Ditte Ristrutturazioni a Saronno"
- This is a directory/listicle page, NOT a competitor
- It appears in search results with a rank
- But it's not useful for competitor tracking

### Root Cause

Google includes list/directory pages in organic results
- User-generated lists
- Directory aggregators
- "Top 10" articles

These clutter competitor analysis.

### Solutions

#### **Option A: Pattern Matching (SIMPLE)**
```python
LIST_KEYWORDS = ['migliori', 'elenco', 'lista', 'top', 'best', 'ranking',
                 'guida', 'directory', 'aggregator']

def is_list_page(title):
    title_lower = title.lower()
    for keyword in LIST_KEYWORDS:
        if keyword in title_lower:
            return True
    return False

# Before saving:
if not is_list_page(competitor['name']):
    save_competitor(competitor)
```

**Pros**: Simple, no false negatives
**Cons**: Can miss some, needs tuning

#### **Option B: Domain Check**
```python
LIST_DOMAINS = ['justdialed.com', 'yellowpages.com', 'yelp.com',
                'tripadvisor.com', 'google.com/maps']

def is_aggregator_domain(url):
    for domain in LIST_DOMAINS:
        if domain in url:
            return True
    return False
```

**Pros**: More accurate
**Cons**: Need to maintain domain list

#### **Option C: Content Analysis**
Check if page looks like a list (more complex):
```python
# Would need to fetch and analyze page content
# Look for multiple competitor names on same page
```

**Pros**: Most accurate
**Cons**: Expensive (extra page fetches)

### Recommendation

**Use Option A + B**:
1. Filter by keywords in title (Option A)
2. Filter by known aggregator domains (Option B)
3. This catches most list pages
4. User can manually review flagged results

---

## Issue 4: Missing Rich Data (Reviews, Ratings, Address, Website, Phone)

### The Problem

Current test data only has:
- competitor_name ✅
- rank ✅
- review_count (empty)
- rating_stars (empty)
- address (empty)
- website (empty)
- phone_number (empty)
- category (empty)

### Root Cause

**Two different API endpoints return different data:**

1. **`/search` endpoint (Organic results)**
   - Returns: title, link, snippet, position
   - Missing: address, phone, rating, reviews

2. **`/places` endpoint (Google Maps / Local Pack)**
   - Returns: name, address, phone, rating, reviews, latitude, longitude
   - Perfect for rich competitor data!

Current code only uses `/search`, missing the local pack data.

### Solution: Use Both Endpoints

#### **Modified `check_rankings_standard()` function:**

```python
def check_rankings_standard(location, business_names, keyword, dummy_mode, cache_only):
    """
    Enhanced to get BOTH organic and local pack results
    """
    # Call 1: Get organic results
    organic_response = call_serper_api(
        url=f"{SERPER_API_URL}/search",
        payload={'q': keyword, 'location': location}
    )

    # Call 2: Get local pack results (has rich data!)
    places_response = call_serper_api(
        url=f"{SERPER_API_URL}/places",
        payload={'q': keyword, 'location': location}
    )

    # Merge data
    competitors = []

    # From places (has ratings, reviews, address, phone)
    if 'places' in places_response:
        competitors.extend(extract_from_places(places_response['places']))

    # From organic (has rank positions)
    if 'organic' in organic_response:
        competitors.extend(extract_from_organic(organic_response['organic']))

    return competitors
```

### Cost Implications

- Each scan currently makes: 2 API calls (search + places per point)
- With both endpoints: 2 calls → no change!
- Actually ALREADY in the code (see `check_rankings_deep()`)

### Data Fields by Endpoint

| Field | /search | /places |
|-------|---------|---------|
| name | ✅ | ✅ |
| address | ❌ | ✅ |
| phone | ❌ | ✅ |
| rating | ❌ | ✅ |
| reviews | ❌ | ✅ |
| latitude | ❌ | ✅ |
| longitude | ❌ | ✅ |
| rank | ✅ | ✅ |

### Recommendation

Make sure `/places` endpoint data is being extracted and saved:
1. Verify `extract_competitors_from_local_pack()` is being called
2. Ensure all fields are mapped correctly
3. Save local pack results to competitor_history with rich data

---

## Issue 5: Need Real Test with Your Actual Business

### Current Test Limitations

- Tested with: "Test Business" (fake name)
- Result: Not found in search results (matched_business_name = NULL)
- Didn't test: Your actual business ranking detection

### What We Need to Test

**Your Business Information:**
1. **Business names to track:**
   - Edil Italia di Sergio Fuscaldo
   - Sergio Fuscaldo
   - Edilitalia

2. **Website:** https://www.ristrutturazionisaronno.it/

3. **Keywords you want to track:**
   - "ristrutturazioni saronno"
   - "ristrutturazioni edil italia"
   - Others?

4. **Service area:**
   - Saronno (and surrounding areas?)

### Real Test Plan

```
PHASE: Proper Business Ranking Test

1. Create project with:
   - Business names: Your actual names
   - Keywords: Your target keywords
   - Website: https://www.ristrutturazionisaronno.it/
   - Area: Saronno

2. Run scan for:
   - 3-5 grid points in Saronno
   - 2-3 keywords
   - Both /search and /places endpoints

3. Verify:
   - ✓ Your business found in results
   - ✓ Correct rank assigned
   - ✓ Local pack data populated (ratings, reviews, address)
   - ✓ Website matches your actual site
   - ✓ Competitors are real, local, not duplicated
   - ✓ Directory pages filtered out

4. Expected Results:
   - Your business: rank 1-10 ideally
   - Competitors: 5-10 real companies
   - Rich data: ratings, reviews, addresses
```

### Do You Want To Provide?

I can run this test if you provide:
1. All variations of your business name
2. List of keywords to track
3. Confirmation of service area boundaries
4. Any other info you want tracked

---

## Summary of Recommended Actions

### HIGH PRIORITY
1. **Enable Local Pack Data** - Modify code to use `/places` endpoint
2. **Normalize Business Names** - Prevent duplicate tracking
3. **Geographic Filtering** - Exclude competitors outside Saronno
4. **Run Real Test** - Test with your actual business

### MEDIUM PRIORITY
5. **Filter List Pages** - Remove directory/listicle results
6. **Add Competitor Aliases UI** - Allow users to mark duplicates
7. **Store Original Names** - Keep unmodified names for reference

### LOW PRIORITY
8. **Advanced Deduplication** - Use fuzzy matching for edge cases
9. **Manual Review UI** - UI for questionable results

---

## Implementation Checklist

- [ ] Understand current app.py flow for competitor extraction
- [ ] Verify `/places` endpoint is being called and data extracted
- [ ] Add name normalization function
- [ ] Add geographic filtering logic
- [ ] Add list-page filtering
- [ ] Provide your business information
- [ ] Run real test with your data
- [ ] Verify all fields populate correctly
- [ ] Validate ranking accuracy
- [ ] Production deployment

---

## Questions for You

1. **Which solution for name deduplication?** A (normalize), B (fuzzy), C (manual), or combination?
2. **List page filtering importance?** Critical or can be handled manually?
3. **Rich data (ratings/reviews)?** Essential or nice-to-have?
4. **Geographic area:**
   - Just Saronno?
   - Saronno + neighboring municipalities?
   - Entire province?

5. **Can you provide:**
   - All your business name variations?
   - Keywords you want to track?
   - Service area boundaries?

---

**Next Step**: Provide your business information and preferences, I'll run a proper test with real data!
