"""Resy API client — venue search, availability, booking, cancellation."""

from __future__ import annotations

from typing import Optional

import requests

from oakley_bookings import auth
from oakley_bookings.common.config import Config
from oakley_bookings.common.cache import FileCache
from oakley_bookings.common.rate_limiter import RateLimiter

_cache = FileCache("resy")
_limiter = RateLimiter(
    max_calls=Config.resy_rate_limit_calls,
    period=Config.resy_rate_limit_period,
)


def _headers() -> dict:
    """Build Resy request headers."""
    creds = auth.get_resy_credentials()
    if not creds:
        raise RuntimeError("Resy credentials not configured. Run: oakley-bookings setup --resy-key KEY --resy-token TOKEN")
    api_key, auth_token = creds
    return {
        "Authorization": f'ResyAPI api_key="{api_key}"',
        "X-Resy-Auth-Token": auth_token,
        "Content-Type": "application/json",
    }


def _get(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make a GET request to the Resy API."""
    _limiter.acquire()
    resp = requests.get(
        f"{Config.resy_base_url}{endpoint}",
        params=params,
        headers=_headers(),
        timeout=Config.request_timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _post(endpoint: str, data: Optional[dict] = None) -> dict:
    """Make a POST request to the Resy API."""
    _limiter.acquire()
    resp = requests.post(
        f"{Config.resy_base_url}{endpoint}",
        json=data,
        headers=_headers(),
        timeout=Config.request_timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ─── Search & Availability ────────────────────────────────────────────────────

def search_venue(name: str, lat: float, lng: float) -> Optional[str]:
    """Search for a venue by name + location. Returns venue_id or None."""
    cache_key = f"venue_search_{name}_{lat}_{lng}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["details"])
    if cached is not None:
        return cached.get("venue_id") if isinstance(cached, dict) else None

    try:
        data = _get("/4/find", params={
            "lat": lat,
            "long": lng,
            "day": "2026-01-01",  # Placeholder — search doesn't filter by date
            "party_size": 2,
        })

        venues = data.get("results", {}).get("venues", [])
        name_lower = name.lower()
        for venue in venues:
            venue_info = venue.get("venue", {})
            venue_name = venue_info.get("name", "").lower()
            if name_lower in venue_name or venue_name in name_lower:
                venue_id = str(venue_info.get("id", ""))
                _cache.set(cache_key, {"venue_id": venue_id, "name": venue_info.get("name", "")})
                return venue_id

        _cache.set(cache_key, {"venue_id": None})
        return None
    except requests.RequestException:
        stale = _cache.get(cache_key)
        if stale is not None:
            return stale.get("venue_id") if isinstance(stale, dict) else None
        return None


def get_availability(venue_id: str, date: str, party_size: int) -> list[dict]:
    """Get available time slots for a venue on a specific date."""
    cache_key = f"avail_{venue_id}_{date}_{party_size}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["availability"])
    if cached is not None:
        return cached if isinstance(cached, list) else []

    try:
        data = _get("/4/find", params={
            "venue_id": venue_id,
            "day": date,
            "party_size": party_size,
        })

        venues = data.get("results", {}).get("venues", [])
        slots = []
        for venue in venues:
            for slot in venue.get("slots", []):
                config = slot.get("config", {})
                date_info = slot.get("date", {})
                slots.append({
                    "config_id": config.get("id", ""),
                    "token": config.get("token", ""),
                    "type": config.get("type", ""),
                    "time": date_info.get("start", ""),
                    "end_time": date_info.get("end", ""),
                })

        _cache.set(cache_key, slots)
        return slots
    except requests.RequestException:
        stale = _cache.get(cache_key)
        if stale is not None:
            return stale if isinstance(stale, list) else []
        return []


def get_venue_details(venue_id: str) -> Optional[dict]:
    """Get detailed venue information."""
    cache_key = f"venue_details_{venue_id}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["details"])
    if cached is not None:
        return cached

    try:
        data = _get("/3/venue", params={"id": venue_id})

        result = {
            "venue_id": str(data.get("id", {}).get("resy", "")),
            "name": data.get("name", ""),
            "type": data.get("type", ""),
            "price_range": data.get("price_range", 0),
            "rating": data.get("rating"),
            "address": (data.get("location", {}) or {}).get("address_1", ""),
            "city": (data.get("location", {}) or {}).get("city", ""),
            "cuisine": data.get("cuisine", []),
            "url_slug": data.get("url_slug", ""),
        }

        _cache.set(cache_key, result)
        return result
    except requests.RequestException:
        stale = _cache.get(cache_key)
        return stale


# ─── Booking Flow ─────────────────────────────────────────────────────────────

def get_booking_details(config_id: str, date: str, party_size: int) -> Optional[dict]:
    """Get booking token and details for a specific config/slot."""
    try:
        data = _post("/3/details", data={
            "config_id": config_id,
            "day": date,
            "party_size": party_size,
        })

        return {
            "book_token": data.get("book_token", {}).get("value", ""),
            "cancellation_policy": data.get("cancellation", {}).get("policy", ""),
            "payment_required": bool(data.get("payment", {}).get("id")),
            "details": data,
        }
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to get booking details: {e}")


def confirm_booking(book_token: str) -> dict:
    """Confirm a booking with the book token."""
    try:
        data = _post("/3/book", data={
            "book_token": book_token,
        })

        return {
            "success": True,
            "resy_token": data.get("resy_token", ""),
            "reservation_id": str(data.get("reservation_id", "")),
            "confirmation": data,
        }
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def get_user_info() -> Optional[dict]:
    """Get current Resy user profile."""
    try:
        data = _get("/2/user")
        return {
            "id": data.get("id"),
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
            "email": data.get("email_address", ""),
            "phone": data.get("mobile_number", ""),
            "payment_methods": data.get("payment_methods", []),
        }
    except requests.RequestException:
        return None


def cancel_booking(resy_token: str) -> dict:
    """Cancel a Resy reservation."""
    try:
        _post("/3/cancel", data={"resy_token": resy_token})
        return {"success": True}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def get_reservations() -> list[dict]:
    """Get current user's Resy reservations."""
    try:
        data = _get("/3/user/reservations")
        reservations = data if isinstance(data, list) else data.get("reservations", [])
        return [
            {
                "reservation_id": str(r.get("reservation_id", "")),
                "resy_token": r.get("resy_token", ""),
                "venue_name": (r.get("venue", {}) or {}).get("name", ""),
                "date": (r.get("date", {}) or {}).get("start", ""),
                "party_size": r.get("num_seats", 0),
                "status": r.get("status", ""),
            }
            for r in reservations
        ]
    except requests.RequestException:
        return []


def test_connection() -> dict:
    """Test Resy API connectivity."""
    try:
        creds = auth.get_resy_credentials()
        if not creds:
            return {"connected": False, "error": "Credentials not configured"}
        user = get_user_info()
        if user:
            return {"connected": True, "status": f"OK (user: {user['first_name']} {user['last_name']})"}
        return {"connected": False, "error": "Could not fetch user info"}
    except Exception as e:
        return {"connected": False, "error": str(e)}
