"""Tests for database CRUD operations."""

import os
import tempfile
import unittest

# Override data dir before importing db
_tmpdir = tempfile.mkdtemp()
os.environ["OAKLEY_BOOKINGS_DATA_DIR"] = _tmpdir

from oakley_bookings import db


class TestBookingCRUD(unittest.TestCase):
    def setUp(self):
        # Reset connection for fresh DB
        db._conn = None

    def test_save_and_get_booking(self):
        booking = {
            "booking_id": "BK_TEST_001",
            "restaurant_name": "Test Restaurant",
            "restaurant_addr": "123 Test St",
            "place_id": "ChIJ_test",
            "date": "2026-02-20",
            "time": "19:30",
            "party_size": 2,
            "platform": "resy",
            "status": "confirmed",
        }
        db.save_booking(booking)

        result = db.get_booking("BK_TEST_001")
        self.assertIsNotNone(result)
        self.assertEqual(result["restaurant_name"], "Test Restaurant")
        self.assertEqual(result["party_size"], 2)
        self.assertEqual(result["platform"], "resy")

    def test_get_booking_not_found(self):
        result = db.get_booking("BK_NONEXISTENT")
        self.assertIsNone(result)

    def test_list_bookings(self):
        booking = {
            "booking_id": "BK_TEST_LIST_001",
            "restaurant_name": "List Test",
            "date": "2026-03-01",
            "time": "20:00",
            "party_size": 4,
            "platform": "opentable",
        }
        db.save_booking(booking)

        results = db.list_bookings()
        self.assertTrue(len(results) > 0)

    def test_update_booking_status(self):
        booking = {
            "booking_id": "BK_TEST_UPDATE",
            "restaurant_name": "Update Test",
            "date": "2026-02-25",
            "time": "18:00",
            "party_size": 2,
            "platform": "phone_only",
        }
        db.save_booking(booking)

        db.update_booking_status("BK_TEST_UPDATE", "cancelled")
        result = db.get_booking("BK_TEST_UPDATE")
        self.assertEqual(result["status"], "cancelled")


class TestRestaurantCRUD(unittest.TestCase):
    def test_save_and_get_restaurant(self):
        restaurant = {
            "place_id": "ChIJ_test_rest",
            "name": "Test Ristorante",
            "address": "456 Test Ave",
            "lat": -33.8688,
            "lng": 151.2093,
            "rating": 4.5,
            "review_count": 200,
            "price_level": "PRICE_LEVEL_MODERATE",
            "platform": "resy",
            "platform_id": "12345",
        }
        db.save_restaurant(restaurant)

        result = db.get_restaurant("ChIJ_test_rest")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Test Ristorante")
        self.assertEqual(result["rating"], 4.5)

    def test_get_restaurant_not_found(self):
        result = db.get_restaurant("ChIJ_nonexistent")
        self.assertIsNone(result)


class TestRatings(unittest.TestCase):
    def test_save_rating(self):
        booking = {
            "booking_id": "BK_TEST_RATE",
            "restaurant_name": "Rating Test",
            "date": "2026-02-15",
            "time": "19:00",
            "party_size": 2,
            "platform": "resy",
        }
        db.save_booking(booking)
        db.save_rating("BK_TEST_RATE", 5, "Excellent!")

        # Booking should be marked completed
        result = db.get_booking("BK_TEST_RATE")
        self.assertEqual(result["status"], "completed")

    def test_get_ratings(self):
        ratings = db.get_ratings()
        self.assertIsInstance(ratings, list)


class TestPreferences(unittest.TestCase):
    def test_set_and_get_preference(self):
        db.update_preference("favourite_cuisine", "Italian")
        prefs = db.get_preferences()
        self.assertEqual(prefs.get("favourite_cuisine"), "Italian")

    def test_update_preference(self):
        db.update_preference("test_key", "value1")
        db.update_preference("test_key", "value2")
        prefs = db.get_preferences()
        self.assertEqual(prefs.get("test_key"), "value2")


class TestStats(unittest.TestCase):
    def test_count_bookings(self):
        count = db.count_bookings()
        self.assertIsInstance(count, int)

    def test_get_top_restaurants(self):
        top = db.get_top_restaurants()
        self.assertIsInstance(top, list)


if __name__ == "__main__":
    unittest.main()
