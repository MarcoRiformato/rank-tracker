import os
import tempfile
import unittest

from rank_tracker.serp import (
    SerpError,
    build_task,
    fetch_local_rank,
    listings_from_response,
    match_business,
    normalize_competitor_name,
    zoom_for_spacing,
)


SAMPLE = {
    "tasks": [{
        "status_code": 20000,
        "status_message": "Ok.",
        "result": [{
            "items": [
                {"type": "maps_paid_item", "rank_group": 1, "title": "Sponsored Co"},
                {
                    "type": "maps_search",
                    "rank_group": 1,
                    "title": "Edil Italia Saronno",
                    "rating": {"value": 4.6, "votes_count": 87},
                    "address": "Via Roma 1",
                    "phone": "+39 02 000",
                    "url": "https://edilitalia.it",
                    "category": "General contractor",
                    "latitude": 45.62,
                    "longitude": 9.03,
                    "place_id": "abc",
                },
                {
                    "type": "maps_search",
                    "rank_group": 2,
                    "title": "Other Shop",
                    "rating": None,
                },
            ]
        }]
    }]
}


class SerpParseTests(unittest.TestCase):
    def test_skips_paid_pins_and_reads_rating(self):
        listings = listings_from_response(SAMPLE)
        self.assertEqual(len(listings), 2)
        self.assertEqual(listings[0]["name"], "Edil Italia Saronno")
        self.assertEqual(listings[0]["rank"], 1)
        self.assertEqual(listings[0]["review_count"], 87)
        self.assertEqual(listings[0]["rating_stars"], 4.6)
        self.assertEqual(listings[0]["type"], "local_pack")
        self.assertIsNone(listings[1]["rating_stars"])

    def test_match_is_case_insensitive_substring(self):
        listings = listings_from_response(SAMPLE)
        rank, name = match_business(listings, ["edil italia"])
        self.assertEqual(rank, 1)
        self.assertEqual(name, "edil italia")
        self.assertEqual(match_business(listings, ["nobody"])[0], None)

    def test_task_error_is_not_parsed_as_listings(self):
        payload = {"tasks": [{"status_code": 40501, "status_message": "Invalid Field"}]}
        with self.assertRaises(SerpError):
            listings_from_response(payload)

    def test_normalize_folds_punctuation(self):
        self.assertEqual(
            normalize_competitor_name("CLA.VI. Ristrutturazioni | Saronno"),
            "CLAVI RISTRUTTURAZIONI SARONNO",
        )

    def test_zoom_tracks_grid_spacing(self):
        self.assertEqual(zoom_for_spacing(0.5), "16z")
        self.assertEqual(zoom_for_spacing(2), "14z")
        self.assertEqual(zoom_for_spacing(8), "12z")

    def test_task_pins_the_coordinate(self):
        task = build_task("ristrutturazione", 45.3157, 8.8564, 2)
        self.assertEqual(task["keyword"], "ristrutturazione")
        self.assertTrue(task["location_coordinate"].startswith("45.3157000,8.8564000,"))
        self.assertFalse(task["search_places"])
        self.assertTrue(task["search_this_area"])
        self.assertLessEqual(task["depth"], 100)

    def test_cache_only_miss_does_not_call_the_api(self):
        previous = os.environ.get("RANK_TRACKER_CACHE_DIR")
        with tempfile.TemporaryDirectory() as folder:
            os.environ["RANK_TRACKER_CACHE_DIR"] = folder
            try:
                result = fetch_local_rank(
                    45.3, 8.8, ["Edil Italia"], "keyword",
                    dummy_mode=False, cache_only=True,
                )
            finally:
                if previous is None:
                    os.environ.pop("RANK_TRACKER_CACHE_DIR", None)
                else:
                    os.environ["RANK_TRACKER_CACHE_DIR"] = previous
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["all_competitors"], [])

    def test_dummy_mode_does_not_need_credentials(self):
        result = fetch_local_rank(
            45.3, 8.8, ["Edil Italia"], "keyword", dummy_mode=True,
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["search_query"], "keyword")
        self.assertTrue(result["all_competitors"])


if __name__ == "__main__":
    unittest.main()
