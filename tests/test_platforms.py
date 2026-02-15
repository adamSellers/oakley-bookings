"""Tests for platform detection and deep link generation."""

import unittest

from oakley_bookings.platforms import (
    detect_platform,
    generate_deep_link,
    get_booking_ease,
    _extract_opentable_rid,
    _extract_quandoo_slug,
)


class TestPlatformDetection(unittest.TestCase):
    def test_opentable_from_website(self):
        result = detect_platform(
            "Test Restaurant", -33.8, 151.2,
            website_url="https://www.opentable.com.au/r/test-restaurant-sydney",
        )
        self.assertEqual(result["platform"], "opentable")
        self.assertGreater(result["confidence"], 0.5)

    def test_quandoo_from_website(self):
        result = detect_platform(
            "Test Restaurant", -33.8, 151.2,
            website_url="https://www.quandoo.com.au/place/test-restaurant-12345",
        )
        self.assertEqual(result["platform"], "quandoo")
        self.assertEqual(result["platform_id"], "test-restaurant-12345")

    def test_phone_only_default(self):
        result = detect_platform(
            "Test Restaurant", -33.8, 151.2,
            website_url="https://testrestaurant.com.au",
        )
        self.assertEqual(result["platform"], "phone_only")
        self.assertIsNone(result["platform_id"])

    def test_resy_from_search_fn(self):
        def mock_resy_search(name, lat, lng):
            return "12345"

        result = detect_platform(
            "Test Restaurant", -33.8, 151.2,
            resy_search_fn=mock_resy_search,
        )
        self.assertEqual(result["platform"], "resy")
        self.assertEqual(result["platform_id"], "12345")

    def test_resy_search_fn_returns_none(self):
        def mock_resy_search(name, lat, lng):
            return None

        result = detect_platform(
            "Test Restaurant", -33.8, 151.2,
            resy_search_fn=mock_resy_search,
        )
        self.assertEqual(result["platform"], "phone_only")

    def test_resy_search_fn_raises(self):
        def mock_resy_search(name, lat, lng):
            raise Exception("API error")

        result = detect_platform(
            "Test Restaurant", -33.8, 151.2,
            resy_search_fn=mock_resy_search,
        )
        self.assertEqual(result["platform"], "phone_only")

    def test_no_website(self):
        result = detect_platform("Test Restaurant", -33.8, 151.2)
        self.assertEqual(result["platform"], "phone_only")


class TestDeepLinkGeneration(unittest.TestCase):
    def test_opentable_link(self):
        link = generate_deep_link("opentable", "12345", "2026-02-20", "19:30", 2)
        self.assertIn("opentable.com.au", link)
        self.assertIn("rid=12345", link)
        self.assertIn("covers=2", link)
        self.assertIn("datetime=2026-02-20T19:30", link)

    def test_quandoo_link(self):
        link = generate_deep_link("quandoo", "test-restaurant-123", "2026-02-20", "19:30", 3)
        self.assertIn("quandoo.com.au", link)
        self.assertIn("test-restaurant-123", link)
        self.assertIn("guests=3", link)

    def test_resy_returns_none(self):
        link = generate_deep_link("resy", "12345")
        self.assertIsNone(link)

    def test_phone_only_returns_none(self):
        link = generate_deep_link("phone_only", None)
        self.assertIsNone(link)

    def test_opentable_no_datetime(self):
        link = generate_deep_link("opentable", "12345")
        self.assertIn("rid=12345", link)
        self.assertNotIn("datetime", link)


class TestExtractors(unittest.TestCase):
    def test_opentable_rid_from_query(self):
        self.assertEqual(
            _extract_opentable_rid("https://www.opentable.com.au/restref/client/?rid=123456"),
            "123456",
        )

    def test_opentable_rid_from_path(self):
        self.assertEqual(
            _extract_opentable_rid("https://www.opentable.com.au/r/test-restaurant-sydney"),
            "test-restaurant-sydney",
        )

    def test_opentable_rid_none(self):
        self.assertIsNone(_extract_opentable_rid("https://example.com"))

    def test_quandoo_slug(self):
        self.assertEqual(
            _extract_quandoo_slug("https://www.quandoo.com.au/place/restaurant-name-12345"),
            "restaurant-name-12345",
        )

    def test_quandoo_slug_none(self):
        self.assertIsNone(_extract_quandoo_slug("https://example.com"))


class TestBookingEase(unittest.TestCase):
    def test_scores(self):
        self.assertEqual(get_booking_ease("resy"), 1.0)
        self.assertEqual(get_booking_ease("opentable"), 0.8)
        self.assertEqual(get_booking_ease("quandoo"), 0.7)
        self.assertEqual(get_booking_ease("phone_only"), 0.3)
        self.assertEqual(get_booking_ease("unknown"), 0.3)


if __name__ == "__main__":
    unittest.main()
