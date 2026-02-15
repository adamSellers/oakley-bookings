---
name: oakley-bookings
description: "Restaurant discovery & booking skill. Search restaurants via Google Places, check availability, book tables via Resy (automated) or deep links (OpenTable, Quandoo), manage bookings, rate visits, and get dining suggestions. Sydney, Australia focused."
requires:
  bins:
    - gog
---

# Oakley Bookings Skill

Restaurant discovery and booking for Sydney, Australia. Search via Google Places, detect booking platforms, book via Resy (automated) or deep links (OpenTable, Quandoo, phone), track bookings, and manage dining history.

## When to Use

- User asks to find a restaurant (cuisine, location, occasion)
- User asks to book, reserve, or get a table
- User asks to check restaurant availability
- User asks about upcoming or past bookings
- User asks to cancel or modify a booking
- User asks to rate a restaurant or dining experience
- User asks for restaurant recommendations or suggestions
- Cron-triggered `remind` for upcoming booking reminders
- Cron-triggered `rate-prompt` for post-dinner rating prompts

## When NOT to Use

- Grocery shopping, food delivery, or takeaway -> not a booking task
- Cooking recipes or meal planning -> not a restaurant task
- Research about food industry or restaurant business -> use **oakley-analyst**
- Content about restaurants for social media -> use **oakley-x**

## Setup

One-time API key configuration:

```bash
# Google Places API key (required — powers all restaurant search)
exec oakley-bookings setup --google-key YOUR_GOOGLE_PLACES_API_KEY

# Optional: Resy credentials (enables automated booking)
exec oakley-bookings setup --resy-key RESY_API_KEY --resy-token RESY_AUTH_TOKEN
```

Verify connectivity:

```bash
exec oakley-bookings status
```

## Commands

Output goes to stdout — use `message` to deliver to Telegram.

Booking commands (`book`, `cancel`, `modify`) require `--confirm` to execute. Without it, they return a preview only. **Never auto-book without explicit user confirmation.**

### status — Health Check

```bash
exec oakley-bookings status
```

Shows version, Google Places/Resy connectivity, booking stats, and data directory.

**When to use:** Quick system check. Run before booking sessions to confirm API access.

### search — Find Restaurants

```bash
exec oakley-bookings search --query "SEARCH TEXT" [--date YYYY-MM-DD] [--time HH:MM] [--party-size N] [--price-range low|mid|high|luxury] [--min-rating N] [--radius METERS] [--sort rating|distance|booking_ease]
```

- `--query` — Search text: cuisine, restaurant name, area (e.g. "Italian Surry Hills", "sushi near Bondi", "fine dining CBD")
- `--date` — Date for availability check (if Resy is available)
- `--time` — Preferred dining time
- `--party-size` — Number of diners (default: 2)
- `--price-range` — Budget filter: `low` ($), `mid` ($$), `high` ($$$), `luxury` ($$$$)
- `--min-rating` — Minimum Google rating (e.g. 4.0)
- `--radius` — Search radius in meters from Sydney CBD (default: 5000)
- `--sort` — Sort results by `rating` (default), `distance`, or `booking_ease`

Returns a numbered list with ratings, price level, distance, booking platform, and available times (Resy venues only).

**Examples:**

```bash
# Find Italian restaurants in Surry Hills
exec oakley-bookings search --query "Italian Surry Hills" --party-size 2

# Find highly-rated restaurants for tonight
exec oakley-bookings search --query "restaurant Sydney CBD" --date 2026-02-16 --time 19:30 --min-rating 4.5

# Find affordable sushi
exec oakley-bookings search --query "sushi Sydney" --price-range low --sort rating
```

**When to use:** User asks to find restaurants, wants dining options, or is exploring cuisines/areas.

### details — Restaurant Details

```bash
exec oakley-bookings details --place-id PLACE_ID
exec oakley-bookings details --name "Restaurant Name"
```

- `--place-id` — Google Places ID (from search results)
- `--name` — Restaurant name (if no place-id; uses search to find it)

Shows full info: rating, price, summary, address, phone, website, Google Maps link, booking platform, opening status, and recent reviews.

**When to use:** User wants more info about a specific restaurant from search results. Use the Place ID from search output.

### check — Check Availability

```bash
exec oakley-bookings check --place-id PLACE_ID --date YYYY-MM-DD --time HH:MM --party-size N
```

- For Resy restaurants: returns specific available time slots
- For OpenTable/Quandoo: returns a deep link to check availability
- For phone-only: returns the phone number

**Example:**

```bash
exec oakley-bookings check --place-id ChIJN1t_tDeuEmsRUsoyG83frY4 --date 2026-02-20 --time 19:30 --party-size 2
```

**When to use:** User wants to see if a specific restaurant has availability before booking.

### book — Book a Table

```bash
exec oakley-bookings book --place-id PLACE_ID --date YYYY-MM-DD --time HH:MM --party-size N [--notes "..."] [--confirm]
```

- `--confirm` — **Required to actually book.** Without it, shows a preview only.
- `--notes` — Booking notes (e.g. "birthday dinner", "window table please")

**Booking behaviour by platform:**
- **Resy**: Automated booking via API. Preview shows restaurant, date, time, party size. Confirm executes the booking.
- **OpenTable/Quandoo**: Returns a pre-filled deep link. User opens the link to complete booking. `--confirm` saves the booking to the local DB for tracking.
- **Phone only**: Returns the phone number. `--confirm` saves the booking to the local DB for tracking.

**Examples:**

```bash
# Preview (always do this first)
exec oakley-bookings book --place-id ChIJN1t_tDeuEmsRUsoyG83frY4 --date 2026-02-20 --time 19:30 --party-size 2

# Confirm the booking
exec oakley-bookings book --place-id ChIJN1t_tDeuEmsRUsoyG83frY4 --date 2026-02-20 --time 19:30 --party-size 2 --notes "anniversary dinner" --confirm
```

**CRITICAL:** Never run with `--confirm` unless the user has explicitly approved the booking preview. Always preview first.

**When to use:** User asks to book, reserve, or make a reservation.

### bookings — List Bookings

```bash
exec oakley-bookings bookings [--upcoming] [--past] [--status confirmed|cancelled|completed]
```

- `--upcoming` — Show future confirmed bookings only
- `--past` — Show past bookings only
- `--status` — Filter by status

**Examples:**

```bash
# Show upcoming bookings
exec oakley-bookings bookings --upcoming

# Show all past bookings
exec oakley-bookings bookings --past
```

**When to use:** User asks about their bookings, upcoming reservations, or dining history.

### cancel — Cancel a Booking

```bash
exec oakley-bookings cancel --booking-id BK_... [--confirm]
```

- `--confirm` — **Required to actually cancel.** Without it, shows a preview.
- For Resy bookings: cancels via API
- For other platforms: updates local DB status (user should also cancel via the platform)

**Example:**

```bash
# Preview
exec oakley-bookings cancel --booking-id BK_1708300000000

# Confirm cancellation
exec oakley-bookings cancel --booking-id BK_1708300000000 --confirm
```

**When to use:** User asks to cancel a reservation.

### modify — Modify a Booking

```bash
exec oakley-bookings modify --booking-id BK_... [--date YYYY-MM-DD] [--time HH:MM] [--party-size N] [--confirm]
```

- Change date, time, and/or party size
- For Resy: cancels old booking + creates new one (Resy has no modify endpoint)
- For other platforms: updates local DB + provides instructions to contact the restaurant

**Example:**

```bash
# Preview modification
exec oakley-bookings modify --booking-id BK_1708300000000 --time 20:00 --party-size 4

# Confirm
exec oakley-bookings modify --booking-id BK_1708300000000 --time 20:00 --party-size 4 --confirm
```

**When to use:** User asks to change a booking's date, time, or party size.

### rate — Rate a Visit

```bash
exec oakley-bookings rate --booking-id BK_... --rating N [--notes "..."]
```

- `--rating` — 1 to 5
- `--notes` — Optional review text

**Example:**

```bash
exec oakley-bookings rate --booking-id BK_1708300000000 --rating 5 --notes "incredible pasta, great service"
```

**When to use:** User shares feedback about a restaurant visit. Also prompted by `rate-prompt` cron.

### remind — Booking Reminders (Cron)

```bash
exec oakley-bookings remind
```

Checks for confirmed bookings in the next 2-4 hours. Outputs a reminder with restaurant name, time, address, and Maps link. Silent (no output) if nothing upcoming.

**When to use:** Called by cron every 30 minutes. Deliver output via `message` if there's a reminder.

### rate-prompt — Post-Dinner Rating Prompt (Cron)

```bash
exec oakley-bookings rate-prompt
```

Checks for confirmed bookings from yesterday that haven't been rated. Prompts the user to rate. Silent if no unrated bookings.

**When to use:** Called by cron daily at 10am. Deliver output via `message` if there are unrated visits.

### suggest — Restaurant Suggestions

```bash
exec oakley-bookings suggest [--cuisine TYPE] [--occasion TYPE]
```

- `--cuisine` — Cuisine preference (e.g. Italian, Japanese, Thai)
- `--occasion` — Occasion type (e.g. "date night", "birthday", "casual")

Suggests restaurants based on past bookings, ratings, and Google Places search.

**Example:**

```bash
exec oakley-bookings suggest --cuisine Japanese --occasion "date night"
```

**When to use:** User asks for restaurant recommendations or is undecided about where to eat.

## Workflows

### Restaurant Search & Booking

The typical multi-turn flow when the user wants to eat out.

**Steps:**

1. **Search** — Find restaurants matching the user's request:
   ```bash
   exec oakley-bookings search --query "Italian Surry Hills" --date 2026-02-20 --time 19:30 --party-size 2
   ```

2. **Present results** — Show the numbered list. Let the user pick by number or name.

3. **Details** — Get full info on the selected restaurant:
   ```bash
   exec oakley-bookings details --place-id ChIJ...
   ```

4. **Check availability** — Verify the slot is available:
   ```bash
   exec oakley-bookings check --place-id ChIJ... --date 2026-02-20 --time 19:30 --party-size 2
   ```

5. **Preview booking** — Show what will be booked:
   ```bash
   exec oakley-bookings book --place-id ChIJ... --date 2026-02-20 --time 19:30 --party-size 2
   ```

6. **Confirm with user** — Present the preview. Only proceed with `--confirm` after explicit user approval.

7. **Book** — Execute the booking:
   ```bash
   exec oakley-bookings book --place-id ChIJ... --date 2026-02-20 --time 19:30 --party-size 2 --notes "anniversary dinner" --confirm
   ```

8. **Calendar entry** — After a successful confirmed booking, create a calendar event:
   ```bash
   exec gog calendar create --title "Dinner at {restaurant_name}" --start "{date}T{time}:00" --duration 2h --location "{address}" --description "Party size: {party_size} | Ref: {booking_id} | Phone: {phone}" --reminder 60m
   ```
   (Requires `GOG_KEYRING_PASSWORD=oakley` env var)

### Booking Modification

1. **List bookings** to find the booking ID:
   ```bash
   exec oakley-bookings bookings --upcoming
   ```

2. **Preview the change**:
   ```bash
   exec oakley-bookings modify --booking-id BK_... --time 20:00
   ```

3. **Confirm** after user approval:
   ```bash
   exec oakley-bookings modify --booking-id BK_... --time 20:00 --confirm
   ```

4. **Update calendar** if needed.

### Cancellation

1. **Preview**:
   ```bash
   exec oakley-bookings cancel --booking-id BK_...
   ```

2. **Confirm** after user approval:
   ```bash
   exec oakley-bookings cancel --booking-id BK_... --confirm
   ```

3. **Delete calendar event** if one was created.

### Rating Collection

After a dining experience (or when `rate-prompt` fires):

1. **Show the prompt** or ask about the experience.

2. **Rate**:
   ```bash
   exec oakley-bookings rate --booking-id BK_... --rating 4 --notes "great ambiance, food was solid"
   ```

## Conversation State

- **Refer to search results by number** — When the user says "book #3" or "tell me about the second one", map the number to the Place ID from the last search.
- **Remember context across turns** — Keep track of the date, time, and party size from the conversation. Don't ask the user to repeat information they've already provided.
- **Booking IDs persist** — Once a booking is made, its `BK_...` ID can be used for cancel, modify, and rate operations.
- **Default to Sydney** — Location defaults to Sydney CBD (-33.8688, 151.2093). No need to ask for location unless the user specifies a different city.
- **Default party size is 2** — Unless the user specifies otherwise.

## Cron Jobs

### Booking Reminders (every 30 minutes)

Schedule: `*/30 * * * *` (Australia/Sydney timezone)

```bash
exec oakley-bookings remind
```

If output is non-empty, deliver via `message`. Silent when no upcoming bookings.

### Rating Prompt (daily at 10am)

Schedule: `0 10 * * *` (Australia/Sydney timezone)

```bash
exec oakley-bookings rate-prompt
```

If output is non-empty, deliver via `message`. Silent when no unrated bookings.

## Error Handling

- **"Google Places API key not configured"** — Run `oakley-bookings setup --google-key KEY`
- **"Resy credentials not configured"** — Run `oakley-bookings setup --resy-key KEY --resy-token TOKEN` (optional — only needed for automated Resy booking)
- **"Google Places search failed"** — API error or quota exceeded. Check the API key and billing in Google Cloud Console.
- **"No restaurants found"** — Broaden the search: remove price/rating filters, increase radius, try different keywords.
- **"No availability on this date"** — Try different dates/times, or check availability via the platform's deep link.
- **"Booking failed"** — Resy booking error. Check if the time slot is still available, or try a different time.
- **"Booking not found"** — Invalid booking ID. Use `bookings --upcoming` to see valid IDs.
- **"Resy: DISCONNECTED"** — Auth token may have expired. Get a fresh token from the Resy website and run `setup` again.
- **Network/timeout errors** — Retry once. If persistent, check internet connectivity.

## Data Storage

- **Database**: `~/.oakley-bookings/data/bookings.db` — SQLite (WAL mode). Bookings, restaurants, ratings, preferences.
- **Cache**: `~/.oakley-bookings/data/cache/` — API response cache (1hr for search, 24hr for details, 5min for availability)
- **Credentials**: `~/.oakley-bookings/data/config.json` — API keys

Set `OAKLEY_BOOKINGS_DATA_DIR` to override the default data location.

## Notes

- **Google Places API (New)** — Uses the newer Places API (`places.googleapis.com/v1`), not the legacy Maps API. Field masking minimises cost. The $200/month free credit covers typical personal use.
- **Resy is optional** — The skill works without Resy credentials. Resy enables automated booking; without it, all restaurants get deep links or phone numbers.
- **Platform detection is conservative** — If unsure about a restaurant's booking platform, it defaults to `phone_only` rather than guessing wrong.
- **Booking ease scores** — Search results are ranked partly by how easy it is to book: Resy (automated) > OpenTable (deep link) > Quandoo (deep link) > phone.
- **Telegram 4096 char limit** — All output is auto-truncated to fit.
- **Calendar integration** — Uses the `gog` CLI (globally installed) for Google Calendar. After a confirmed booking, create a calendar event with the restaurant details. `gog` handles OAuth separately.
- **Rate limiting** — Google Places: 10 req/s. Resy: 5 req/s. Do not call search commands in rapid loops.
