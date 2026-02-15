"""Platform detection & deep link generation for booking platforms."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote


def detect_platform(
    restaurant_name: str,
    lat: float,
    lng: float,
    website_url: Optional[str] = None,
    resy_search_fn=None,
) -> dict:
    """Detect which booking platform a restaurant uses.

    Returns: {platform, platform_id, confidence}
    """
    # Check website URL for platform clues
    if website_url:
        url_lower = website_url.lower()

        # OpenTable
        if "opentable" in url_lower:
            rid = _extract_opentable_rid(website_url)
            return {
                "platform": "opentable",
                "platform_id": rid,
                "confidence": 0.9 if rid else 0.7,
            }

        # Quandoo
        if "quandoo" in url_lower:
            slug = _extract_quandoo_slug(website_url)
            return {
                "platform": "quandoo",
                "platform_id": slug,
                "confidence": 0.9 if slug else 0.7,
            }

    # Check Resy (API search)
    if resy_search_fn is not None:
        try:
            venue_id = resy_search_fn(restaurant_name, lat, lng)
            if venue_id:
                return {
                    "platform": "resy",
                    "platform_id": venue_id,
                    "confidence": 0.8,
                }
        except Exception:
            pass  # Resy not available, continue

    # Default: phone only
    return {
        "platform": "phone_only",
        "platform_id": None,
        "confidence": 1.0,
    }


def generate_deep_link(
    platform: str,
    platform_id: Optional[str],
    date: Optional[str] = None,
    time: Optional[str] = None,
    party_size: int = 2,
) -> Optional[str]:
    """Generate a booking deep link for the given platform."""
    if platform == "opentable" and platform_id:
        return _opentable_link(platform_id, date, time, party_size)

    if platform == "quandoo" and platform_id:
        return _quandoo_link(platform_id, date, time, party_size)

    if platform == "resy":
        # Resy handles booking via API, not deep links
        return None

    return None


def _extract_opentable_rid(url: str) -> Optional[str]:
    """Extract OpenTable restaurant ID from URL."""
    # Pattern: opentable.com/...?rid=12345 or opentable.com.au/r/...
    match = re.search(r'rid[=:](\d+)', url)
    if match:
        return match.group(1)
    # Try path-based: /r/restaurant-name-city
    match = re.search(r'opentable\.com(?:\.\w+)?/r/([\w-]+)', url)
    if match:
        return match.group(1)
    return None


def _extract_quandoo_slug(url: str) -> Optional[str]:
    """Extract Quandoo slug from URL."""
    # Pattern: quandoo.com.au/place/slug-12345
    match = re.search(r'quandoo\.com(?:\.\w+)?/place/([\w-]+)', url)
    if match:
        return match.group(1)
    return None


def _opentable_link(
    rid: str,
    date: Optional[str] = None,
    time: Optional[str] = None,
    party_size: int = 2,
) -> str:
    """Generate OpenTable booking link."""
    base = f"https://www.opentable.com.au/restref/client/?rid={rid}&covers={party_size}"
    if date and time:
        # OpenTable expects datetime in ISO-like format
        base += f"&datetime={date}T{time}"
    return base


def _quandoo_link(
    slug: str,
    date: Optional[str] = None,
    time: Optional[str] = None,
    party_size: int = 2,
) -> str:
    """Generate Quandoo booking link."""
    base = f"https://www.quandoo.com.au/place/{slug}"
    params = []
    if date:
        params.append(f"date={date}")
    if time:
        params.append(f"time={time}")
    if party_size:
        params.append(f"guests={party_size}")
    if params:
        base += "?" + "&".join(params)
    return base


# ─── Scoring ──────────────────────────────────────────────────────────────────

BOOKING_EASE_SCORES = {
    "resy": 1.0,
    "opentable": 0.8,
    "quandoo": 0.7,
    "google_reserve": 0.6,
    "phone_only": 0.3,
}


def get_booking_ease(platform: str) -> float:
    """Return a booking ease score for ranking purposes."""
    return BOOKING_EASE_SCORES.get(platform, 0.3)
