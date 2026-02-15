"""Tests for formatting utilities."""

import unittest

from oakley_bookings.common.formatting import (
    format_rating,
    format_price_level,
    truncate_for_telegram,
    format_section_header,
    format_list_item,
)


class TestFormatRating(unittest.TestCase):
    def test_rating_with_reviews(self):
        self.assertEqual(format_rating(4.5, 1234), "4.5/5 (1,234 reviews)")

    def test_rating_without_reviews(self):
        self.assertEqual(format_rating(4.0), "4.0/5")

    def test_rating_rounds_to_half(self):
        self.assertEqual(format_rating(4.3), "4.5/5")
        self.assertEqual(format_rating(4.7), "4.5/5")
        self.assertEqual(format_rating(4.8), "5.0/5")

    def test_rating_none(self):
        self.assertEqual(format_rating(None), "No rating")

    def test_rating_zero_reviews(self):
        self.assertEqual(format_rating(3.5, 0), "3.5/5 (0 reviews)")


class TestFormatPriceLevel(unittest.TestCase):
    def test_inexpensive(self):
        self.assertEqual(format_price_level("PRICE_LEVEL_INEXPENSIVE"), "$")

    def test_moderate(self):
        self.assertEqual(format_price_level("PRICE_LEVEL_MODERATE"), "$$")

    def test_expensive(self):
        self.assertEqual(format_price_level("PRICE_LEVEL_EXPENSIVE"), "$$$")

    def test_very_expensive(self):
        self.assertEqual(format_price_level("PRICE_LEVEL_VERY_EXPENSIVE"), "$$$$")

    def test_free(self):
        self.assertEqual(format_price_level("PRICE_LEVEL_FREE"), "Free")

    def test_none(self):
        self.assertEqual(format_price_level(None), "Price N/A")

    def test_unknown(self):
        self.assertEqual(format_price_level("UNKNOWN"), "UNKNOWN")


class TestTruncateForTelegram(unittest.TestCase):
    def test_short_text_unchanged(self):
        text = "Hello world"
        self.assertEqual(truncate_for_telegram(text), text)

    def test_long_text_truncated(self):
        text = "x" * 5000
        result = truncate_for_telegram(text)
        self.assertLessEqual(len(result), 4096)
        self.assertTrue(result.endswith("... (truncated)"))

    def test_truncation_at_newline(self):
        lines = ["line " + str(i) for i in range(500)]
        text = "\n".join(lines)
        result = truncate_for_telegram(text)
        self.assertLessEqual(len(result), 4096)
        self.assertTrue(result.endswith("... (truncated)"))


class TestFormatHelpers(unittest.TestCase):
    def test_section_header(self):
        self.assertEqual(format_section_header("Test"), "**Test**")

    def test_list_item(self):
        self.assertEqual(format_list_item("item"), "- item")

    def test_list_item_indented(self):
        self.assertEqual(format_list_item("item", indent=2), "    - item")


if __name__ == "__main__":
    unittest.main()
