"""Booking engine — Resy auto-book, deep links for others."""

from __future__ import annotations

import time
from typing import Optional

from oakley_bookings import auth, db, resy_client
from oakley_bookings.common.config import Config
from oakley_bookings.platforms import generate_deep_link


def check_availability(
    place_id: str,
    date: str,
    time_str: str,
    party_size: int,
) -> dict:
    """Check availability for a restaurant.

    Returns: {available, platform, slots, deep_link, message}
    """
    restaurant = db.get_restaurant(place_id)
    if not restaurant:
        # Try to find from a fresh search
        from oakley_bookings import discovery
        details = discovery.get_restaurant_details(place_id=place_id)
        if details:
            restaurant = {
                "place_id": details["place_id"],
                "name": details["name"],
                "platform": details.get("platform", "phone_only"),
                "platform_id": details.get("platform_id"),
                "phone": details.get("phone", ""),
                "website": details.get("website", ""),
                "google_maps_url": details.get("google_maps_url", ""),
            }
        else:
            return {"available": False, "message": f"Restaurant not found: {place_id}"}

    platform = restaurant.get("platform", "phone_only")
    platform_id = restaurant.get("platform_id")

    # Resy: check actual availability
    if platform == "resy" and platform_id and auth.has_resy_credentials():
        slots = resy_client.get_availability(platform_id, date, party_size)
        if slots:
            # Filter for slots near requested time
            matching = _filter_time_slots(slots, time_str)
            return {
                "available": True,
                "platform": "resy",
                "restaurant_name": restaurant.get("name", ""),
                "slots": matching if matching else slots,
                "all_slots": slots,
                "message": f"{len(slots)} time slots available",
            }
        return {
            "available": False,
            "platform": "resy",
            "restaurant_name": restaurant.get("name", ""),
            "slots": [],
            "message": "No availability on this date",
        }

    # Other platforms: return deep link
    deep_link = generate_deep_link(platform, platform_id, date, time_str, party_size)
    return {
        "available": None,  # Unknown — check at link
        "platform": platform,
        "restaurant_name": restaurant.get("name", ""),
        "deep_link": deep_link,
        "phone": restaurant.get("phone", ""),
        "message": f"Check availability via {platform}" + (f": {deep_link}" if deep_link else ""),
    }


def book(
    place_id: str,
    date: str,
    time_str: str,
    party_size: int,
    confirm: bool = False,
    notes: Optional[str] = None,
) -> dict:
    """Book a table at a restaurant.

    Without confirm=True, returns a preview only.
    With confirm=True, executes the booking (Resy) or returns deep link (others).
    """
    # Get restaurant info
    restaurant = db.get_restaurant(place_id)
    if not restaurant:
        from oakley_bookings import discovery
        details = discovery.get_restaurant_details(place_id=place_id)
        if details:
            restaurant = {
                "place_id": details["place_id"],
                "name": details["name"],
                "address": details.get("address", ""),
                "platform": details.get("platform", "phone_only"),
                "platform_id": details.get("platform_id"),
                "phone": details.get("phone", ""),
                "website": details.get("website", ""),
                "google_maps_url": details.get("google_maps_url", ""),
            }
            # Cache in DB
            db.save_restaurant(details)
        else:
            return {"success": False, "reason": f"Restaurant not found: {place_id}"}

    platform = restaurant.get("platform", "phone_only")
    platform_id = restaurant.get("platform_id")

    # Resy automated booking
    if platform == "resy" and platform_id and auth.has_resy_credentials():
        return _book_resy(restaurant, platform_id, date, time_str, party_size, confirm, notes)

    # Other platforms: deep link
    deep_link = generate_deep_link(platform, platform_id, date, time_str, party_size)

    if not confirm:
        return {
            "success": True,
            "preview": True,
            "restaurant_name": restaurant.get("name", ""),
            "date": date,
            "time": time_str,
            "party_size": party_size,
            "platform": platform,
            "deep_link": deep_link,
            "phone": restaurant.get("phone", ""),
            "message": f"Book via {platform}" + (f": {deep_link}" if deep_link else f" — call {restaurant.get('phone', 'N/A')}"),
        }

    # For non-Resy, save a manual booking record
    booking_id = f"BK_{int(time.time() * 1000)}"
    db.save_booking({
        "booking_id": booking_id,
        "restaurant_name": restaurant.get("name", ""),
        "restaurant_addr": restaurant.get("address", ""),
        "place_id": place_id,
        "date": date,
        "time": time_str,
        "party_size": party_size,
        "platform": platform,
        "status": "confirmed",
        "google_maps_url": restaurant.get("google_maps_url", ""),
        "phone": restaurant.get("phone", ""),
        "notes": notes,
    })

    return {
        "success": True,
        "preview": False,
        "booking_id": booking_id,
        "restaurant_name": restaurant.get("name", ""),
        "date": date,
        "time": time_str,
        "party_size": party_size,
        "platform": platform,
        "deep_link": deep_link,
        "message": f"Booking recorded. Complete booking via {platform}" +
                   (f": {deep_link}" if deep_link else f" — call {restaurant.get('phone', 'N/A')}"),
    }


def _book_resy(
    restaurant: dict,
    venue_id: str,
    date: str,
    time_str: str,
    party_size: int,
    confirm: bool,
    notes: Optional[str],
) -> dict:
    """Execute a Resy booking."""
    # Get available slots
    slots = resy_client.get_availability(venue_id, date, party_size)
    if not slots:
        return {"success": False, "reason": "No availability on this date"}

    # Find the best matching slot
    matching = _filter_time_slots(slots, time_str)
    if not matching:
        # No exact match — show what's available
        all_times = [s["time"] for s in slots if s.get("time")]
        return {
            "success": False,
            "reason": f"No slot at {time_str}. Available: {', '.join(all_times[:6])}",
        }

    slot = matching[0]

    if not confirm:
        return {
            "success": True,
            "preview": True,
            "restaurant_name": restaurant.get("name", ""),
            "date": date,
            "time": slot["time"],
            "party_size": party_size,
            "platform": "resy",
            "config_id": slot["config_id"],
            "message": f"Ready to book {restaurant.get('name', '')} on {date} at {slot['time']} for {party_size}",
        }

    # Get booking token
    try:
        details = resy_client.get_booking_details(slot["config_id"], date, party_size)
        if not details or not details.get("book_token"):
            return {"success": False, "reason": "Could not get booking token"}
    except RuntimeError as e:
        return {"success": False, "reason": str(e)}

    # Confirm the booking
    result = resy_client.confirm_booking(details["book_token"])
    if not result.get("success"):
        return {"success": False, "reason": result.get("error", "Booking failed")}

    # Save to DB
    booking_id = f"BK_{int(time.time() * 1000)}"
    db.save_booking({
        "booking_id": booking_id,
        "restaurant_name": restaurant.get("name", ""),
        "restaurant_addr": restaurant.get("address", ""),
        "place_id": restaurant.get("place_id", ""),
        "date": date,
        "time": slot["time"],
        "party_size": party_size,
        "platform": "resy",
        "platform_ref": result.get("reservation_id", ""),
        "status": "confirmed",
        "google_maps_url": restaurant.get("google_maps_url", ""),
        "phone": restaurant.get("phone", ""),
        "notes": notes,
    })

    return {
        "success": True,
        "preview": False,
        "booking_id": booking_id,
        "restaurant_name": restaurant.get("name", ""),
        "date": date,
        "time": slot["time"],
        "party_size": party_size,
        "platform": "resy",
        "reservation_id": result.get("reservation_id", ""),
        "message": f"Booked {restaurant.get('name', '')} on {date} at {slot['time']} for {party_size}",
    }


def cancel(booking_id: str, confirm: bool = False) -> dict:
    """Cancel a booking."""
    booking = db.get_booking(booking_id)
    if not booking:
        return {"success": False, "reason": f"Booking not found: {booking_id}"}

    if booking["status"] == "cancelled":
        return {"success": False, "reason": "Booking is already cancelled"}

    if not confirm:
        return {
            "success": True,
            "preview": True,
            "booking_id": booking_id,
            "restaurant_name": booking["restaurant_name"],
            "date": booking["date"],
            "time": booking["time"],
            "party_size": booking["party_size"],
            "platform": booking["platform"],
            "message": f"Cancel {booking['restaurant_name']} on {booking['date']} at {booking['time']}?",
        }

    # Resy: cancel via API
    if booking["platform"] == "resy" and booking.get("platform_ref") and auth.has_resy_credentials():
        result = resy_client.cancel_booking(booking["platform_ref"])
        if not result.get("success"):
            return {"success": False, "reason": f"Resy cancellation failed: {result.get('error', '')}"}

    db.update_booking_status(booking_id, "cancelled")

    return {
        "success": True,
        "preview": False,
        "booking_id": booking_id,
        "restaurant_name": booking["restaurant_name"],
        "message": f"Cancelled: {booking['restaurant_name']} on {booking['date']} at {booking['time']}",
    }


def modify(
    booking_id: str,
    new_date: Optional[str] = None,
    new_time: Optional[str] = None,
    new_party_size: Optional[int] = None,
    confirm: bool = False,
) -> dict:
    """Modify a booking (Resy: cancel + rebook; others: instructions)."""
    booking = db.get_booking(booking_id)
    if not booking:
        return {"success": False, "reason": f"Booking not found: {booking_id}"}

    if booking["status"] != "confirmed":
        return {"success": False, "reason": f"Cannot modify booking with status: {booking['status']}"}

    use_date = new_date or booking["date"]
    use_time = new_time or booking["time"]
    use_party = new_party_size or booking["party_size"]

    if not confirm:
        return {
            "success": True,
            "preview": True,
            "booking_id": booking_id,
            "restaurant_name": booking["restaurant_name"],
            "original": {"date": booking["date"], "time": booking["time"], "party_size": booking["party_size"]},
            "modified": {"date": use_date, "time": use_time, "party_size": use_party},
            "platform": booking["platform"],
            "message": f"Modify {booking['restaurant_name']}: {booking['date']} {booking['time']} ({booking['party_size']}p) → {use_date} {use_time} ({use_party}p)?",
        }

    # Resy: cancel old + book new
    if booking["platform"] == "resy" and auth.has_resy_credentials():
        # Cancel the old booking
        cancel_result = cancel(booking_id, confirm=True)
        if not cancel_result.get("success"):
            return {"success": False, "reason": f"Could not cancel original: {cancel_result.get('reason', '')}"}

        # Book the new one
        book_result = book(
            booking["place_id"], use_date, use_time, use_party,
            confirm=True, notes=booking.get("notes"),
        )
        if not book_result.get("success"):
            return {"success": False, "reason": f"New booking failed: {book_result.get('reason', '')} (old booking was cancelled)"}

        return {
            "success": True,
            "preview": False,
            "old_booking_id": booking_id,
            "new_booking_id": book_result.get("booking_id"),
            "restaurant_name": booking["restaurant_name"],
            "message": f"Modified: {booking['restaurant_name']} now on {use_date} at {book_result.get('time', use_time)} for {use_party}",
        }

    # Non-Resy: update DB record + return instructions
    db.update_booking_status(
        booking_id, "confirmed",
        date=use_date, time=use_time, party_size=use_party,
    )

    deep_link = generate_deep_link(booking["platform"], None, use_date, use_time, use_party)
    return {
        "success": True,
        "preview": False,
        "booking_id": booking_id,
        "restaurant_name": booking["restaurant_name"],
        "deep_link": deep_link,
        "phone": booking.get("phone", ""),
        "message": f"DB updated. Contact {booking['restaurant_name']} to confirm the change" +
                   (f" — call {booking.get('phone', '')}" if booking.get("phone") else ""),
    }


def _filter_time_slots(slots: list[dict], target_time: str) -> list[dict]:
    """Filter and sort slots by proximity to target time."""
    if not target_time or not slots:
        return slots

    try:
        target_h, target_m = int(target_time.split(":")[0]), int(target_time.split(":")[1])
        target_minutes = target_h * 60 + target_m
    except (ValueError, IndexError):
        return slots

    scored = []
    for slot in slots:
        slot_time = slot.get("time", "")
        try:
            # Resy times can be like "19:30:00" or "7:30 PM" or "19:30"
            parts = slot_time.replace(":00:00", ":00").split(":")
            if len(parts) >= 2:
                s_h, s_m = int(parts[0]), int(parts[1][:2])
                slot_minutes = s_h * 60 + s_m
                diff = abs(slot_minutes - target_minutes)
                scored.append((diff, slot))
        except (ValueError, IndexError):
            scored.append((9999, slot))

    scored.sort(key=lambda x: x[0])
    return [s[1] for s in scored if s[0] <= 120]  # Within 2 hours
