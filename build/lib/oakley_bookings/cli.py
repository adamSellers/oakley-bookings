"""Unified CLI dispatcher for all oakley-bookings commands."""

import argparse
import sys


# ─── Phase 1: Setup & Status ─────────────────────────────────────────────────

def cmd_setup(args):
    from oakley_bookings import auth

    if not args.google_key and not args.resy_key:
        print("Error: Provide --google-key and/or --resy-key + --resy-token.", file=sys.stderr)
        sys.exit(1)

    if args.google_key:
        auth.save_google_key(args.google_key)
        print("Google Places API key saved.")

        from oakley_bookings.google_places import test_connection
        result = test_connection()
        if result["connected"]:
            print(f"Google Places: OK")
        else:
            print(f"Google Places: FAILED — {result['error']}")

    if args.resy_key:
        if not args.resy_token:
            print("Error: --resy-token is required with --resy-key.", file=sys.stderr)
            sys.exit(1)
        auth.save_resy_credentials(args.resy_key, args.resy_token)
        print("Resy credentials saved.")

        from oakley_bookings.resy_client import test_connection as resy_test
        result = resy_test()
        if result["connected"]:
            print(f"Resy: {result['status']}")
        else:
            print(f"Resy: FAILED — {result['error']}")


def cmd_status(args):
    from oakley_bookings import __version__, auth, db
    from oakley_bookings.common import Config, format_datetime_aest

    Config.ensure_dirs()

    lines = [
        f"Oakley Bookings v{__version__}",
        f"Time: {format_datetime_aest()}",
        "",
    ]

    # Google Places
    if auth.has_google_key():
        from oakley_bookings.google_places import test_connection
        gp = test_connection()
        if gp["connected"]:
            lines.append("Google Places: connected")
        else:
            lines.append(f"Google Places: DISCONNECTED — {gp['error']}")
    else:
        lines.append("Google Places: NOT CONFIGURED")
        lines.append("  Run: oakley-bookings setup --google-key KEY")

    # Resy
    if auth.has_resy_credentials():
        from oakley_bookings.resy_client import test_connection as resy_test
        resy = resy_test()
        if resy["connected"]:
            lines.append(f"Resy: {resy['status']}")
        else:
            lines.append(f"Resy: DISCONNECTED — {resy['error']}")
    else:
        lines.append("Resy: not configured (optional)")

    # DB stats
    try:
        total = db.count_bookings()
        confirmed = db.count_bookings("confirmed")
        lines.append("")
        lines.append(f"Total bookings: {total}")
        lines.append(f"Confirmed: {confirmed}")
    except Exception:
        lines.append("")
        lines.append("Database: not initialized")

    lines.append("")
    lines.append(f"Data directory: {Config.data_dir}")

    print("\n".join(lines))


# ─── Phase 2: Search & Details ────────────────────────────────────────────────

def cmd_search(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header, format_rating, format_price_level
    from oakley_bookings import discovery

    results = discovery.search(
        query=args.query,
        date=args.date,
        time=args.time,
        party_size=args.party_size,
        price_range=args.price_range,
        min_rating=args.min_rating,
        radius_m=args.radius,
        sort_by=args.sort,
    )

    if not results:
        print("No restaurants found matching your search.")
        return

    lines = [format_section_header(f"Restaurant Search ({len(results)} results)"), ""]

    for i, r in enumerate(results, 1):
        name = r.get("name", "Unknown")
        rating = format_rating(r.get("rating"), r.get("review_count"))
        price = format_price_level(r.get("price_level"))
        platform = r.get("platform", "phone_only")
        distance = r.get("distance_km", "?")

        platform_badge = {
            "resy": "RESY",
            "opentable": "OpenTable",
            "quandoo": "Quandoo",
            "phone_only": "Phone",
        }.get(platform, platform)

        lines.append(f"{i}. {name}")
        lines.append(f"   {rating} | {price} | {distance}km | {platform_badge}")

        if r.get("address"):
            lines.append(f"   {r['address']}")

        # Show available times for Resy
        if r.get("available_times"):
            times_str = ", ".join(r["available_times"][:6])
            lines.append(f"   Available: {times_str}")

        lines.append(f"   ID: {r.get('place_id', 'N/A')}")
        lines.append("")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_details(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header, format_rating, format_price_level
    from oakley_bookings import discovery

    details = discovery.get_restaurant_details(
        place_id=args.place_id,
        name=args.name,
    )

    if not details:
        print("Restaurant not found.", file=sys.stderr)
        sys.exit(1)

    name = details.get("name", "Unknown")
    lines = [format_section_header(name), ""]

    lines.append(f"Rating: {format_rating(details.get('rating'), details.get('review_count'))}")
    lines.append(f"Price: {format_price_level(details.get('price_level'))}")

    if details.get("editorial_summary"):
        lines.append(f"Summary: {details['editorial_summary']}")

    if details.get("address"):
        lines.append(f"Address: {details['address']}")
    if details.get("phone"):
        lines.append(f"Phone: {details['phone']}")
    if details.get("website"):
        lines.append(f"Website: {details['website']}")
    if details.get("google_maps_url"):
        lines.append(f"Maps: {details['google_maps_url']}")

    platform = details.get("platform", "phone_only")
    platform_label = {
        "resy": "Resy (automated booking)",
        "opentable": "OpenTable (deep link)",
        "quandoo": "Quandoo (deep link)",
        "phone_only": "Phone/walk-in",
    }.get(platform, platform)
    lines.append(f"Booking: {platform_label}")

    if details.get("open_now") is not None:
        lines.append(f"Open now: {'Yes' if details['open_now'] else 'No'}")

    # Reviews
    if details.get("reviews"):
        lines.append("")
        lines.append(format_section_header("Recent Reviews"))
        for rev in details["reviews"][:3]:
            author = rev.get("author", "Anonymous")
            rating = rev.get("rating", "?")
            text = rev.get("text", "")[:120]
            lines.append(f"  {author} ({rating}/5): {text}")

    lines.append("")
    lines.append(f"Place ID: {details.get('place_id', 'N/A')}")

    print(truncate_for_telegram("\n".join(lines)))


# ─── Phase 3: Booking Engine ─────────────────────────────────────────────────

def cmd_check(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header
    from oakley_bookings import booking

    result = booking.check_availability(
        place_id=args.place_id,
        date=args.date,
        time_str=args.time,
        party_size=args.party_size,
    )

    lines = [format_section_header(f"Availability: {result.get('restaurant_name', 'Unknown')}"), ""]
    lines.append(f"Platform: {result.get('platform', 'unknown')}")

    if result.get("slots"):
        lines.append(f"Available slots ({len(result['slots'])}):")
        for slot in result["slots"][:8]:
            lines.append(f"  {slot.get('time', '?')} ({slot.get('type', '')})")
    elif result.get("deep_link"):
        lines.append(f"Check here: {result['deep_link']}")
    elif result.get("phone"):
        lines.append(f"Call: {result['phone']}")

    lines.append("")
    lines.append(result.get("message", ""))

    print(truncate_for_telegram("\n".join(lines)))


def cmd_book(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header
    from oakley_bookings import booking

    result = booking.book(
        place_id=args.place_id,
        date=args.date,
        time_str=args.time,
        party_size=args.party_size,
        confirm=args.confirm,
        notes=args.notes,
    )

    if not result.get("success"):
        print(f"Booking failed: {result.get('reason', 'unknown error')}", file=sys.stderr)
        sys.exit(1)

    if result.get("preview"):
        lines = [
            format_section_header("Booking Preview"),
            "",
            f"Restaurant: {result.get('restaurant_name', 'Unknown')}",
            f"Date: {result.get('date', 'N/A')}",
            f"Time: {result.get('time', 'N/A')}",
            f"Party size: {result.get('party_size', 'N/A')}",
            f"Platform: {result.get('platform', 'N/A')}",
            "",
            "Add --confirm to book.",
        ]
    else:
        prefix = "BOOKED" if result.get("platform") == "resy" else "BOOKING RECORDED"
        lines = [
            format_section_header(prefix),
            "",
            f"Booking ID: {result.get('booking_id', 'N/A')}",
            f"Restaurant: {result.get('restaurant_name', 'Unknown')}",
            f"Date: {result.get('date', 'N/A')}",
            f"Time: {result.get('time', 'N/A')}",
            f"Party size: {result.get('party_size', 'N/A')}",
            f"Platform: {result.get('platform', 'N/A')}",
        ]
        if result.get("deep_link"):
            lines.append(f"Complete booking: {result['deep_link']}")

    lines.append("")
    lines.append(result.get("message", ""))

    print(truncate_for_telegram("\n".join(lines)))


# ─── Phase 4: Booking Management ─────────────────────────────────────────────

def cmd_bookings(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header
    from oakley_bookings import db

    bookings = db.list_bookings(
        status=args.status,
        upcoming=args.upcoming,
        past=args.past,
    )

    if not bookings:
        print("No bookings found.")
        return

    label = "Upcoming" if args.upcoming else "Past" if args.past else "All"
    lines = [format_section_header(f"Bookings — {label} ({len(bookings)})"), ""]

    for b in bookings:
        status_badge = {
            "confirmed": "",
            "cancelled": " [CANCELLED]",
            "completed": " [COMPLETED]",
            "modified": " [MODIFIED]",
        }.get(b["status"], f" [{b['status'].upper()}]")

        lines.append(f"{b['restaurant_name']}{status_badge}")
        lines.append(f"  {b['date']} at {b['time']} | {b['party_size']}p | {b['platform']}")
        if b.get("notes"):
            lines.append(f"  Note: {b['notes']}")
        lines.append(f"  ID: {b['booking_id']}")
        lines.append("")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_cancel(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header
    from oakley_bookings import booking

    result = booking.cancel(args.booking_id, confirm=args.confirm)

    if not result.get("success"):
        print(f"Cancel failed: {result.get('reason', 'unknown error')}", file=sys.stderr)
        sys.exit(1)

    if result.get("preview"):
        lines = [
            format_section_header("Cancel Preview"),
            "",
            f"Restaurant: {result.get('restaurant_name', 'Unknown')}",
            f"Date: {result.get('date', 'N/A')}",
            f"Time: {result.get('time', 'N/A')}",
            f"Party size: {result.get('party_size', 'N/A')}",
            "",
            "Add --confirm to cancel.",
        ]
    else:
        lines = [result.get("message", "Cancelled.")]

    print(truncate_for_telegram("\n".join(lines)))


def cmd_modify(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header
    from oakley_bookings import booking

    result = booking.modify(
        booking_id=args.booking_id,
        new_date=args.date,
        new_time=args.time,
        new_party_size=args.party_size,
        confirm=args.confirm,
    )

    if not result.get("success"):
        print(f"Modify failed: {result.get('reason', 'unknown error')}", file=sys.stderr)
        sys.exit(1)

    if result.get("preview"):
        orig = result.get("original", {})
        mod = result.get("modified", {})
        lines = [
            format_section_header("Modify Preview"),
            "",
            f"Restaurant: {result.get('restaurant_name', 'Unknown')}",
            f"From: {orig.get('date', 'N/A')} at {orig.get('time', 'N/A')} ({orig.get('party_size', '?')}p)",
            f"To:   {mod.get('date', 'N/A')} at {mod.get('time', 'N/A')} ({mod.get('party_size', '?')}p)",
            "",
            "Add --confirm to modify.",
        ]
    else:
        lines = [result.get("message", "Modified.")]

    print(truncate_for_telegram("\n".join(lines)))


def cmd_rate(args):
    from oakley_bookings import db

    booking = db.get_booking(args.booking_id)
    if not booking:
        print(f"Error: Booking '{args.booking_id}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.rating < 1 or args.rating > 5:
        print("Error: Rating must be 1-5.", file=sys.stderr)
        sys.exit(1)

    db.save_rating(args.booking_id, args.rating, args.notes)
    print(f"Rated {booking['restaurant_name']}: {args.rating}/5")
    if args.notes:
        print(f"Note: {args.notes}")


# ─── Phase 5: Proactive Features ─────────────────────────────────────────────

def cmd_remind(args):
    from oakley_bookings import db
    from oakley_bookings.common import now_aest

    now = now_aest()
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    current_minute = now.minute

    # Get today's confirmed bookings
    bookings = db.list_bookings(status="confirmed")
    upcoming = []

    for b in bookings:
        if b["date"] != today:
            continue
        try:
            bh, bm = int(b["time"].split(":")[0]), int(b["time"].split(":")[1])
            booking_minutes = bh * 60 + bm
            current_minutes = current_hour * 60 + current_minute
            diff = booking_minutes - current_minutes
            if 0 < diff <= 240:  # 0-4 hours from now
                upcoming.append((diff, b))
        except (ValueError, IndexError):
            continue

    if not upcoming:
        # Silent — cron job, no output when nothing to remind
        return

    upcoming.sort(key=lambda x: x[0])

    lines = []
    for diff, b in upcoming:
        hours = diff // 60
        mins = diff % 60
        time_str = f"{hours}h {mins}m" if hours else f"{mins}m"

        lines.append(f"Reminder: {b['restaurant_name']} in {time_str}")
        lines.append(f"  Time: {b['time']} | Party: {b['party_size']}p")
        if b.get("restaurant_addr"):
            lines.append(f"  Address: {b['restaurant_addr']}")
        if b.get("google_maps_url"):
            lines.append(f"  Maps: {b['google_maps_url']}")
        if b.get("phone"):
            lines.append(f"  Phone: {b['phone']}")
        lines.append("")

    print("\n".join(lines).rstrip())


def cmd_suggest(args):
    from oakley_bookings.common import truncate_for_telegram, format_section_header, format_rating
    from oakley_bookings import db, discovery

    lines = [format_section_header("Restaurant Suggestions"), ""]

    # Get top-rated restaurants from history
    top = db.get_top_restaurants(limit=5)
    if top:
        lines.append("Your favourites:")
        for r in top:
            avg = r.get("avg_rating")
            rating_str = f" ({avg:.1f}/5)" if avg else ""
            lines.append(f"  {r['restaurant_name']}{rating_str} — visited {r['visit_count']}x")
        lines.append("")

    # Try fresh suggestions if Google API is available
    try:
        query = args.cuisine if args.cuisine else "popular restaurant"
        if args.occasion:
            query = f"{args.occasion} {query}"

        results = discovery.search(query=query, min_rating=4.0, max_results=5)
        if results:
            lines.append("Suggestions:")
            for i, r in enumerate(results, 1):
                rating = format_rating(r.get("rating"), r.get("review_count"))
                lines.append(f"  {i}. {r.get('name', 'Unknown')} — {rating}")
                if r.get("address"):
                    lines.append(f"     {r['address']}")
                lines.append(f"     ID: {r.get('place_id', 'N/A')}")
            lines.append("")
    except Exception:
        if not top:
            lines.append("No suggestions available. Search for restaurants first!")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_rate_prompt(args):
    from oakley_bookings import db

    unrated = db.get_unrated_past_bookings()
    if not unrated:
        # Silent — cron job
        return

    lines = ["How was dinner? Rate your recent visits:", ""]
    for b in unrated:
        lines.append(f"  {b['restaurant_name']} ({b['date']} at {b['time']})")
        lines.append(f"  Rate: oakley-bookings rate --booking-id {b['booking_id']} --rating N")
        lines.append("")

    print("\n".join(lines).rstrip())


# ─── Main dispatcher ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="oakley-bookings",
        description="Oakley Bookings — restaurant discovery & booking via Google Places + Resy",
    )
    subparsers = parser.add_subparsers(dest="command")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Configure API keys")
    setup_parser.add_argument("--google-key", default=None, help="Google Places API key")
    setup_parser.add_argument("--resy-key", default=None, help="Resy API key")
    setup_parser.add_argument("--resy-token", default=None, help="Resy auth token")

    # status
    subparsers.add_parser("status", help="Show version, API connectivity, booking stats")

    # search
    search_parser = subparsers.add_parser("search", help="Search for restaurants")
    search_parser.add_argument("--query", required=True, help="Search text (cuisine, name, area)")
    search_parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (for availability)")
    search_parser.add_argument("--time", default=None, help="Time HH:MM (for availability)")
    search_parser.add_argument("--party-size", type=int, default=2, help="Number of diners (default: 2)")
    search_parser.add_argument("--price-range", default=None, help="low|mid|high|luxury")
    search_parser.add_argument("--min-rating", type=float, default=None, help="Minimum Google rating (e.g. 4.0)")
    search_parser.add_argument("--radius", type=int, default=5000, help="Search radius in meters (default: 5000)")
    search_parser.add_argument("--sort", default="rating", help="Sort by: rating|distance|booking_ease")

    # details
    details_parser = subparsers.add_parser("details", help="Get restaurant details")
    details_parser.add_argument("--place-id", default=None, help="Google Places ID")
    details_parser.add_argument("--name", default=None, help="Restaurant name (if no place-id)")

    # check
    check_parser = subparsers.add_parser("check", help="Check table availability")
    check_parser.add_argument("--place-id", required=True, help="Google Places ID")
    check_parser.add_argument("--date", required=True, help="Date YYYY-MM-DD")
    check_parser.add_argument("--time", required=True, help="Time HH:MM")
    check_parser.add_argument("--party-size", type=int, default=2, help="Number of diners (default: 2)")

    # book
    book_parser = subparsers.add_parser("book", help="Book a table")
    book_parser.add_argument("--place-id", required=True, help="Google Places ID")
    book_parser.add_argument("--date", required=True, help="Date YYYY-MM-DD")
    book_parser.add_argument("--time", required=True, help="Time HH:MM")
    book_parser.add_argument("--party-size", type=int, default=2, help="Number of diners (default: 2)")
    book_parser.add_argument("--confirm", action="store_true", help="Actually book (default: preview only)")
    book_parser.add_argument("--notes", default=None, help="Booking notes (e.g. birthday dinner)")

    # bookings
    bookings_parser = subparsers.add_parser("bookings", help="List bookings")
    bookings_parser.add_argument("--upcoming", action="store_true", help="Show upcoming bookings only")
    bookings_parser.add_argument("--past", action="store_true", help="Show past bookings only")
    bookings_parser.add_argument("--status", default=None, help="Filter by status: confirmed|cancelled|completed")

    # cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a booking")
    cancel_parser.add_argument("--booking-id", required=True, help="Booking ID")
    cancel_parser.add_argument("--confirm", action="store_true", help="Actually cancel (default: preview only)")

    # modify
    modify_parser = subparsers.add_parser("modify", help="Modify a booking")
    modify_parser.add_argument("--booking-id", required=True, help="Booking ID")
    modify_parser.add_argument("--date", default=None, help="New date YYYY-MM-DD")
    modify_parser.add_argument("--time", default=None, help="New time HH:MM")
    modify_parser.add_argument("--party-size", type=int, default=None, help="New party size")
    modify_parser.add_argument("--confirm", action="store_true", help="Actually modify (default: preview only)")

    # rate
    rate_parser = subparsers.add_parser("rate", help="Rate a restaurant visit")
    rate_parser.add_argument("--booking-id", required=True, help="Booking ID")
    rate_parser.add_argument("--rating", type=int, required=True, help="Rating 1-5")
    rate_parser.add_argument("--notes", default=None, help="Optional review notes")

    # remind (cron)
    subparsers.add_parser("remind", help="Check for upcoming bookings (cron)")

    # rate-prompt (cron)
    subparsers.add_parser("rate-prompt", help="Prompt for ratings on past bookings (cron)")

    # suggest
    suggest_parser = subparsers.add_parser("suggest", help="Get restaurant suggestions")
    suggest_parser.add_argument("--cuisine", default=None, help="Cuisine type (e.g. Italian, Japanese)")
    suggest_parser.add_argument("--occasion", default=None, help="Occasion (e.g. date night, birthday)")

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "status": cmd_status,
        "search": cmd_search,
        "details": cmd_details,
        "check": cmd_check,
        "book": cmd_book,
        "bookings": cmd_bookings,
        "cancel": cmd_cancel,
        "modify": cmd_modify,
        "rate": cmd_rate,
        "remind": cmd_remind,
        "rate-prompt": cmd_rate_prompt,
        "suggest": cmd_suggest,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
