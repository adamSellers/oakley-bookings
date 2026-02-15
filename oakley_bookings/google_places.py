"""Google Places API (New) client — restaurant search and details."""

from __future__ import annotations

from typing import Optional

import requests

from oakley_bookings import auth
from oakley_bookings.common.config import Config
from oakley_bookings.common.cache import FileCache
from oakley_bookings.common.rate_limiter import RateLimiter

_cache = FileCache("google_places")
_limiter = RateLimiter(
    max_calls=Config.google_rate_limit_calls,
    period=Config.google_rate_limit_period,
)

# Field masks for controlling response size and cost
_SEARCH_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.googleMapsUri",
    "places.websiteUri",
    "places.internationalPhoneNumber",
    "places.currentOpeningHours",
    "places.primaryType",
])

_DETAILS_FIELD_MASK = ",".join([
    "id",
    "displayName",
    "formattedAddress",
    "rating",
    "userRatingCount",
    "priceLevel",
    "googleMapsUri",
    "websiteUri",
    "internationalPhoneNumber",
    "currentOpeningHours",
    "primaryType",
    "reviews",
    "location",
    "editorialSummary",
    "shortFormattedAddress",
])

_NEARBY_FIELD_MASK = _SEARCH_FIELD_MASK


def _headers() -> dict:
    """Build request headers with API key."""
    key = auth.get_google_key()
    if not key:
        raise RuntimeError("Google Places API key not configured. Run: oakley-bookings setup --google-key KEY")
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
    }


def _parse_place(place: dict) -> dict:
    """Normalise a Places API place object into a flat dict."""
    display_name = place.get("displayName", {})
    hours = place.get("currentOpeningHours", {})

    return {
        "place_id": place.get("id", ""),
        "name": display_name.get("text", "Unknown"),
        "address": place.get("formattedAddress", ""),
        "short_address": place.get("shortFormattedAddress", ""),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "price_level": place.get("priceLevel"),
        "google_maps_url": place.get("googleMapsUri", ""),
        "website": place.get("websiteUri", ""),
        "phone": place.get("internationalPhoneNumber", ""),
        "primary_type": place.get("primaryType", ""),
        "open_now": hours.get("openNow"),
        "location": place.get("location", {}),
        "editorial_summary": (place.get("editorialSummary") or {}).get("text", ""),
    }


def search_restaurants(
    query: str,
    lat: float = Config.default_lat,
    lng: float = Config.default_lng,
    radius_m: int = Config.default_radius_m,
    price_levels: Optional[list[str]] = None,
    min_rating: Optional[float] = None,
    open_now: bool = False,
    max_results: int = 10,
) -> list[dict]:
    """Search for restaurants via Places API Text Search."""
    cache_key = f"search_{query}_{lat}_{lng}_{radius_m}_{open_now}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["search"])
    if cached is not None:
        return cached if isinstance(cached, list) else cached.get("results", [])

    body = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
        "includedType": "restaurant",
        "maxResultCount": max_results,
        "languageCode": "en",
    }

    if open_now:
        body["openNow"] = True

    if price_levels:
        body["priceLevels"] = price_levels

    headers = _headers()
    headers["X-Goog-FieldMask"] = _SEARCH_FIELD_MASK

    _limiter.acquire()
    try:
        resp = requests.post(
            f"{Config.google_places_base_url}/places:searchText",
            json=body,
            headers=headers,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        # Try stale cache on error
        stale = _cache.get(cache_key)
        if stale is not None:
            results = stale if isinstance(stale, list) else stale.get("results", [])
            return results
        raise RuntimeError(f"Google Places search failed: {e}")

    places = data.get("places", [])
    results = [_parse_place(p) for p in places]

    # Filter by min_rating client-side
    if min_rating is not None:
        results = [r for r in results if r.get("rating") and r["rating"] >= min_rating]

    _cache.set(cache_key, results)
    return results


def get_details(place_id: str) -> dict:
    """Get full details for a specific place."""
    cache_key = f"details_{place_id}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["details"])
    if cached is not None:
        return cached

    headers = _headers()
    headers["X-Goog-FieldMask"] = _DETAILS_FIELD_MASK

    _limiter.acquire()
    try:
        resp = requests.get(
            f"{Config.google_places_base_url}/places/{place_id}",
            headers=headers,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        stale = _cache.get(cache_key)
        if stale is not None:
            return stale
        raise RuntimeError(f"Google Places details failed: {e}")

    result = _parse_place(data)

    # Include reviews if present
    reviews = data.get("reviews", [])
    result["reviews"] = [
        {
            "author": (r.get("authorAttribution") or {}).get("displayName", ""),
            "rating": r.get("rating"),
            "text": (r.get("text") or {}).get("text", ""),
            "time": r.get("publishTime", ""),
        }
        for r in reviews[:5]
    ]

    _cache.set(cache_key, result)
    return result


def nearby_restaurants(
    lat: float = Config.default_lat,
    lng: float = Config.default_lng,
    radius_m: int = Config.default_radius_m,
    cuisine_type: Optional[str] = None,
    max_results: int = 10,
) -> list[dict]:
    """Search for nearby restaurants via Places API Nearby Search."""
    cache_key = f"nearby_{lat}_{lng}_{radius_m}_{cuisine_type}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["search"])
    if cached is not None:
        return cached if isinstance(cached, list) else cached.get("results", [])

    body = {
        "includedTypes": ["restaurant"],
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
        "maxResultCount": max_results,
        "languageCode": "en",
    }

    headers = _headers()
    headers["X-Goog-FieldMask"] = _NEARBY_FIELD_MASK

    _limiter.acquire()
    try:
        resp = requests.post(
            f"{Config.google_places_base_url}/places:searchNearby",
            json=body,
            headers=headers,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        stale = _cache.get(cache_key)
        if stale is not None:
            results = stale if isinstance(stale, list) else stale.get("results", [])
            return results
        raise RuntimeError(f"Google Places nearby search failed: {e}")

    places = data.get("places", [])
    results = [_parse_place(p) for p in places]

    _cache.set(cache_key, results)
    return results


def test_connection() -> dict:
    """Test Google Places API connectivity with a minimal request."""
    try:
        key = auth.get_google_key()
        if not key:
            return {"connected": False, "error": "API key not configured"}

        headers = _headers()
        headers["X-Goog-FieldMask"] = "places.id"

        resp = requests.post(
            f"{Config.google_places_base_url}/places:searchText",
            json={"textQuery": "restaurant Sydney", "maxResultCount": 1},
            headers=headers,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        return {"connected": True, "status": "OK"}
    except requests.RequestException as e:
        return {"connected": False, "error": str(e)}
