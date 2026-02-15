"""Search orchestration — Google Places + platform matching + ranking."""

from __future__ import annotations

import math
from typing import Optional

from oakley_bookings import auth, google_places, resy_client
from oakley_bookings.common.config import Config
from oakley_bookings.common.cache import FileCache
from oakley_bookings.platforms import detect_platform, get_booking_ease

_cache = FileCache("discovery")


def search(
    query: str,
    lat: float = Config.default_lat,
    lng: float = Config.default_lng,
    radius_m: int = Config.default_radius_m,
    date: Optional[str] = None,
    time: Optional[str] = None,
    party_size: int = Config.default_party_size,
    price_range: Optional[str] = None,
    min_rating: Optional[float] = None,
    sort_by: str = "rating",
    max_results: int = 10,
) -> list[dict]:
    """Search for restaurants with platform detection and ranking.

    Args:
        query: Search text (cuisine, name, area)
        lat, lng: Center point for location bias
        radius_m: Search radius in meters
        date: YYYY-MM-DD for availability check
        time: HH:MM for availability check
        party_size: Number of diners
        price_range: low/mid/high/luxury
        min_rating: Minimum Google rating
        sort_by: rating|distance|booking_ease
        max_results: Maximum results to return
    """
    # Map price_range to Google price levels
    price_levels = _map_price_range(price_range)

    # 1. Query Google Places
    places = google_places.search_restaurants(
        query=query,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        price_levels=price_levels,
        min_rating=min_rating,
        max_results=max_results,
    )

    if not places:
        return []

    # 2. Detect booking platform for top results (max 8 to limit API calls)
    resy_search_fn = resy_client.search_venue if auth.has_resy_credentials() else None
    results = []

    for place in places[:8]:
        place_lat = (place.get("location") or {}).get("latitude", lat)
        place_lng = (place.get("location") or {}).get("longitude", lng)

        platform_info = detect_platform(
            restaurant_name=place["name"],
            lat=place_lat,
            lng=place_lng,
            website_url=place.get("website"),
            resy_search_fn=resy_search_fn,
        )

        # 3. For Resy matches, fetch availability if date provided
        available_times = []
        if platform_info["platform"] == "resy" and date and platform_info["platform_id"]:
            try:
                slots = resy_client.get_availability(
                    platform_info["platform_id"], date, party_size,
                )
                available_times = [s["time"] for s in slots if s.get("time")]
            except Exception:
                pass

        # 4. Build result
        distance_km = _haversine(lat, lng, place_lat, place_lng)

        result = {
            **place,
            "platform": platform_info["platform"],
            "platform_id": platform_info["platform_id"],
            "platform_confidence": platform_info["confidence"],
            "available_times": available_times,
            "distance_km": round(distance_km, 1),
            "booking_ease": get_booking_ease(platform_info["platform"]),
        }
        results.append(result)

    # 5. Score and rank
    results = _rank_results(results, sort_by)

    return results


def get_restaurant_details(place_id: Optional[str] = None, name: Optional[str] = None) -> Optional[dict]:
    """Get full restaurant details with platform info."""
    if place_id:
        details = google_places.get_details(place_id)
    elif name:
        # Search by name to find place_id
        results = google_places.search_restaurants(query=name, max_results=1)
        if not results:
            return None
        details = google_places.get_details(results[0]["place_id"])
    else:
        return None

    if not details:
        return None

    # Detect platform
    place_lat = (details.get("location") or {}).get("latitude", Config.default_lat)
    place_lng = (details.get("location") or {}).get("longitude", Config.default_lng)

    resy_search_fn = resy_client.search_venue if auth.has_resy_credentials() else None
    platform_info = detect_platform(
        restaurant_name=details["name"],
        lat=place_lat,
        lng=place_lng,
        website_url=details.get("website"),
        resy_search_fn=resy_search_fn,
    )

    details["platform"] = platform_info["platform"]
    details["platform_id"] = platform_info["platform_id"]
    details["platform_confidence"] = platform_info["confidence"]

    return details


def _rank_results(results: list[dict], sort_by: str) -> list[dict]:
    """Score and rank search results."""
    if not results:
        return results

    # Normalise review counts for scoring (0-1)
    max_reviews = max((r.get("review_count") or 0) for r in results) or 1

    for r in results:
        rating = r.get("rating") or 0
        reviews_norm = (r.get("review_count") or 0) / max_reviews
        proximity = max(0, 1 - (r.get("distance_km", 5) / 10))  # 0-1, closer = higher
        booking_ease = r.get("booking_ease", 0.3)

        r["_score"] = (
            (rating / 5) * 0.4 +
            reviews_norm * 0.2 +
            proximity * 0.2 +
            booking_ease * 0.2
        )

    if sort_by == "distance":
        results.sort(key=lambda r: r.get("distance_km", 999))
    elif sort_by == "booking_ease":
        results.sort(key=lambda r: r.get("booking_ease", 0), reverse=True)
    else:  # default: rating
        results.sort(key=lambda r: r.get("_score", 0), reverse=True)

    return results


def _map_price_range(price_range: Optional[str]) -> Optional[list[str]]:
    """Map user-friendly price range to Google Places price levels."""
    if not price_range:
        return None
    mapping = {
        "low": ["PRICE_LEVEL_INEXPENSIVE"],
        "mid": ["PRICE_LEVEL_MODERATE"],
        "high": ["PRICE_LEVEL_EXPENSIVE"],
        "luxury": ["PRICE_LEVEL_VERY_EXPENSIVE"],
    }
    return mapping.get(price_range.lower())


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in km."""
    R = 6371  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2 +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
