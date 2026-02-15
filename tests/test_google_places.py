"""Tests for Google Places response parsing (no API calls)."""

import unittest

from oakley_bookings.google_places import _parse_place


class TestParsePlace(unittest.TestCase):
    def test_full_place(self):
        place = {
            "id": "ChIJ_test123",
            "displayName": {"text": "Test Restaurant", "languageCode": "en"},
            "formattedAddress": "123 Test St, Sydney NSW 2000",
            "shortFormattedAddress": "123 Test St",
            "rating": 4.5,
            "userRatingCount": 500,
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "googleMapsUri": "https://maps.google.com/test",
            "websiteUri": "https://testrestaurant.com",
            "internationalPhoneNumber": "+61 2 1234 5678",
            "primaryType": "restaurant",
            "currentOpeningHours": {"openNow": True},
            "location": {"latitude": -33.8688, "longitude": 151.2093},
            "editorialSummary": {"text": "A great test restaurant"},
        }

        result = _parse_place(place)

        self.assertEqual(result["place_id"], "ChIJ_test123")
        self.assertEqual(result["name"], "Test Restaurant")
        self.assertEqual(result["address"], "123 Test St, Sydney NSW 2000")
        self.assertEqual(result["short_address"], "123 Test St")
        self.assertEqual(result["rating"], 4.5)
        self.assertEqual(result["review_count"], 500)
        self.assertEqual(result["price_level"], "PRICE_LEVEL_MODERATE")
        self.assertEqual(result["google_maps_url"], "https://maps.google.com/test")
        self.assertEqual(result["website"], "https://testrestaurant.com")
        self.assertEqual(result["phone"], "+61 2 1234 5678")
        self.assertEqual(result["primary_type"], "restaurant")
        self.assertTrue(result["open_now"])
        self.assertEqual(result["editorial_summary"], "A great test restaurant")
        self.assertEqual(result["location"]["latitude"], -33.8688)

    def test_minimal_place(self):
        place = {
            "id": "ChIJ_minimal",
            "displayName": {"text": "Minimal"},
        }

        result = _parse_place(place)

        self.assertEqual(result["place_id"], "ChIJ_minimal")
        self.assertEqual(result["name"], "Minimal")
        self.assertEqual(result["address"], "")
        self.assertIsNone(result["rating"])
        self.assertIsNone(result["review_count"])
        self.assertIsNone(result["open_now"])

    def test_empty_place(self):
        result = _parse_place({})
        self.assertEqual(result["place_id"], "")
        self.assertEqual(result["name"], "Unknown")

    def test_missing_display_name(self):
        place = {"id": "test"}
        result = _parse_place(place)
        self.assertEqual(result["name"], "Unknown")

    def test_no_editorial_summary(self):
        place = {"id": "test", "displayName": {"text": "Test"}}
        result = _parse_place(place)
        self.assertEqual(result["editorial_summary"], "")


if __name__ == "__main__":
    unittest.main()
