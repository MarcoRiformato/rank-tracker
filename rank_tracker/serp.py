"""DataForSEO Google Maps provider.

One Live Maps request per grid point. The keyword is searched at that
coordinate. Rank is the maps_search position, which is the local pack rank
this app stores.
"""

import hashlib
import json
import os
import random

import requests
from dotenv import load_dotenv

load_dotenv()

MAPS_LIVE_URL = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"
TASK_OK = 20000


class SerpError(Exception):
    """DataForSEO rejected the call or returned a task error."""


def credentials_configured():
    return bool(_login() and _password())


def normalize_competitor_name(name):
    """Fold a listing title so 'A.B.C. | Foo' and 'ABC Foo' dedupe."""
    if not name:
        return ""
    normalized = name.strip().upper().replace(".", "").replace("|", "").replace("-", " ")
    normalized = "".join(c for c in normalized if c.isalnum() or c.isspace())
    return " ".join(normalized.split())


def zoom_for_spacing(spacing_km):
    """Map viewport slightly wider than one grid cell."""
    if spacing_km <= 0.5:
        return "16z"
    if spacing_km <= 1:
        return "15z"
    if spacing_km <= 2:
        return "14z"
    if spacing_km <= 5:
        return "13z"
    return "12z"


def build_task(keyword, lat, lon, spacing_km):
    device = os.getenv("DATAFORSEO_DEVICE", "mobile").strip().lower()
    if device not in ("desktop", "mobile"):
        device = "mobile"
    return {
        "keyword": keyword,
        "language_code": os.getenv("DATAFORSEO_LANGUAGE_CODE", "it").strip() or "it",
        "location_coordinate": f"{float(lat):.7f},{float(lon):.7f},{zoom_for_spacing(spacing_km)}",
        "device": device,
        "depth": _depth(),
        "search_this_area": True,
        # Local-intent keywords drift to a famous place when this stays on.
        "search_places": False,
        "se_domain": os.getenv("DATAFORSEO_SE_DOMAIN", "google.it").strip() or "google.it",
    }


def listings_from_response(payload):
    """maps_search rows only. Paid pins are a separate rank group and are skipped."""
    if not isinstance(payload, dict):
        raise SerpError("DataForSEO response was not an object")
    tasks = payload.get("tasks") or []
    if not tasks:
        raise SerpError(payload.get("status_message") or "DataForSEO response had no tasks")
    task = tasks[0]
    if task.get("status_code") != TASK_OK:
        code = task.get("status_code")
        message = task.get("status_message") or "task failed"
        raise SerpError(f"DataForSEO {code}: {message}")
    results = task.get("result") or []
    if not results:
        return []
    items = results[0].get("items") or []
    listings = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict) or item.get("type") != "maps_search":
            continue
        rating = item.get("rating") or {}
        if not isinstance(rating, dict):
            rating = {}
        category = item.get("category") or ""
        if isinstance(category, list):
            category = ", ".join(str(part) for part in category)
        rank = item.get("rank_group") or idx
        listings.append({
            "name": item.get("title") or "",
            "rank": int(rank),
            "type": "local_pack",
            "review_count": _as_int(rating.get("votes_count")),
            "rating_stars": _as_float(rating.get("value")),
            "address": item.get("address") or "",
            "phone_number": item.get("phone") or "",
            "website": item.get("url") or "",
            "category": category,
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "place_id": item.get("place_id"),
        })
    return listings


def match_business(listings, business_names):
    """First listing whose title or website contains a business name."""
    names = [(name, name.lower()) for name in business_names if name and name.strip()]
    for listing in listings:
        title = (listing.get("name") or "").lower()
        website = (listing.get("website") or "").lower()
        for original, needle in names:
            if needle in title or needle in website:
                return listing.get("rank"), original
    return None, None


def fetch_local_rank(lat, lon, business_names, keyword, grid_spacing=2.0, dummy_mode=False, cache_only=False):
    """
    Rank one grid point.

    Returns local_pack_rank, organic_rank (always None; Maps has no web results),
    matched_business_name, status, all_competitors, search_query.
    API failures come back as status 'error' and do not raise.
    """
    keyword = (keyword or "").strip()
    names = list(business_names or [])
    if dummy_mode:
        return _dummy_result(names, keyword)

    task = build_task(keyword, lat, lon, grid_spacing)
    cached = _read_cache(task)
    if cached is None:
        if cache_only:
            return _error_result("No cached DataForSEO result for this point", keyword)
        try:
            cached = post_maps(task)
            listings = listings_from_response(cached)
        except SerpError as exc:
            return _error_result(str(exc), keyword)
        _write_cache(task, cached)
    else:
        try:
            listings = listings_from_response(cached)
        except SerpError as exc:
            return _error_result(str(exc), keyword)

    rank, matched = match_business(listings, names)
    return {
        "local_pack_rank": rank,
        "organic_rank": None,
        "matched_business_name": matched,
        "status": "success",
        "all_competitors": listings,
        "search_query": keyword,
    }


def post_maps(task):
    if not credentials_configured():
        raise SerpError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are not set")
    try:
        response = requests.post(
            MAPS_LIVE_URL,
            json=[task],
            auth=(_login(), _password()),
            timeout=120,
        )
    except requests.RequestException as exc:
        raise SerpError(f"DataForSEO request failed: {exc}") from exc
    if response.status_code >= 400:
        raise SerpError(f"DataForSEO HTTP {response.status_code}: {response.text[:300]}")
    try:
        return response.json()
    except ValueError as exc:
        raise SerpError("DataForSEO returned invalid JSON") from exc


def _login():
    return os.getenv("DATAFORSEO_LOGIN", "").strip()


def _password():
    return os.getenv("DATAFORSEO_PASSWORD", "").strip()


def _depth():
    try:
        depth = int(os.getenv("DATAFORSEO_DEPTH", "20"))
    except ValueError:
        depth = 20
    # Depth above 100 is billed as extra SERPs.
    return max(1, min(depth, 100))


def _cache_path(task):
    digest = hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest()
    folder = os.getenv("RANK_TRACKER_CACHE_DIR", os.path.join("cache", "dataforseo"))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, digest + ".json")


def _read_cache(task):
    path = _cache_path(task)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(task, payload):
    path = _cache_path(task)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(temporary, path)


def _error_result(message, keyword):
    return {
        "local_pack_rank": None,
        "organic_rank": None,
        "matched_business_name": None,
        "status": "error",
        "error": message,
        "all_competitors": [],
        "search_query": keyword,
    }


def _dummy_result(business_names, keyword):
    primary = next((name for name in business_names if name and name.strip()), "Example Business")
    rank = random.choice([1, 2, 3, 4, 7, 11, None])
    competitors = []
    example_n = 1
    for position in range(1, 11):
        if rank == position:
            name = primary
        else:
            name = f"Example Business {example_n}"
            example_n += 1
        competitors.append({
            "name": name,
            "rank": position,
            "type": "local_pack",
            "review_count": 20 * position,
            "rating_stars": 4.2,
            "address": "",
            "phone_number": "",
            "website": "",
            "category": "",
            "latitude": None,
            "longitude": None,
        })
    return {
        "local_pack_rank": rank,
        "organic_rank": None,
        "matched_business_name": primary if rank else None,
        "status": "success",
        "all_competitors": competitors,
        "search_query": keyword,
    }


def _as_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
