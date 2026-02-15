"""Tests for discovery ranking and helper functions."""

import unittest

from oakley_bookings.discovery import _haversine, _map_price_range, _rank_results


class TestHaversine(unittest.TestCase):
    def test_same_point(self):
        dist = _haversine(-33.8688, 151.2093, -33.8688, 151.2093)
        self.assertAlmostEqual(dist, 0, places=1)

    def test_sydney_to_bondi(self):
        # Sydney CBD to Bondi Beach ~= 7km
        dist = _haversine(-33.8688, 151.2093, -33.8915, 151.2767)
        self.assertGreater(dist, 5)
        self.assertLess(dist, 10)

    def test_sydney_to_parramatta(self):
        # Sydney CBD to Parramatta ~= 23km
        dist = _haversine(-33.8688, 151.2093, -33.8151, 151.0011)
        self.assertGreater(dist, 15)
        self.assertLess(dist, 30)


class TestMapPriceRange(unittest.TestCase):
    def test_low(self):
        self.assertEqual(_map_price_range("low"), ["PRICE_LEVEL_INEXPENSIVE"])

    def test_mid(self):
        self.assertEqual(_map_price_range("mid"), ["PRICE_LEVEL_MODERATE"])

    def test_high(self):
        self.assertEqual(_map_price_range("high"), ["PRICE_LEVEL_EXPENSIVE"])

    def test_luxury(self):
        self.assertEqual(_map_price_range("luxury"), ["PRICE_LEVEL_VERY_EXPENSIVE"])

    def test_none(self):
        self.assertIsNone(_map_price_range(None))

    def test_unknown(self):
        self.assertIsNone(_map_price_range("unknown"))

    def test_case_insensitive(self):
        self.assertEqual(_map_price_range("LOW"), ["PRICE_LEVEL_INEXPENSIVE"])
        self.assertEqual(_map_price_range("Mid"), ["PRICE_LEVEL_MODERATE"])


class TestRankResults(unittest.TestCase):
    def test_empty_results(self):
        self.assertEqual(_rank_results([], "rating"), [])

    def test_ranking_by_rating(self):
        results = [
            {"name": "A", "rating": 4.0, "review_count": 50, "distance_km": 2, "booking_ease": 0.3},
            {"name": "B", "rating": 5.0, "review_count": 100, "distance_km": 1, "booking_ease": 0.3},
        ]
        ranked = _rank_results(results, "rating")
        self.assertEqual(ranked[0]["name"], "B")  # Higher rating + more reviews

    def test_ranking_by_distance(self):
        results = [
            {"name": "Far", "rating": 5.0, "review_count": 100, "distance_km": 10, "booking_ease": 1.0},
            {"name": "Near", "rating": 3.0, "review_count": 10, "distance_km": 1, "booking_ease": 0.3},
        ]
        ranked = _rank_results(results, "distance")
        self.assertEqual(ranked[0]["name"], "Near")

    def test_ranking_by_booking_ease(self):
        results = [
            {"name": "Phone", "rating": 5.0, "review_count": 100, "distance_km": 1, "booking_ease": 0.3},
            {"name": "Resy", "rating": 4.0, "review_count": 50, "distance_km": 2, "booking_ease": 1.0},
        ]
        ranked = _rank_results(results, "booking_ease")
        self.assertEqual(ranked[0]["name"], "Resy")

    def test_score_added_to_results(self):
        results = [
            {"name": "A", "rating": 4.5, "review_count": 100, "distance_km": 2, "booking_ease": 0.8},
        ]
        ranked = _rank_results(results, "rating")
        self.assertIn("_score", ranked[0])
        self.assertGreater(ranked[0]["_score"], 0)


if __name__ == "__main__":
    unittest.main()
