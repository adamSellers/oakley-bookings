# oakley-bookings

Restaurant discovery & booking CLI for [OpenClaw](https://openclaw.dev). Searches via Google Places, books via Resy (automated) or deep links (OpenTable, Quandoo), and tracks dining history. Sydney, Australia focused with geolocation support.

## Architecture

```
Google Places API ──> Discovery (search, details, ratings)
                        │
                        v
                  Platform Detection
                  (Resy? OpenTable? Quandoo? Phone only?)
                        │
             ┌──────────┼──────────┐──────────┐
             v          v          v          v
          Resy      OpenTable   Quandoo    Fallback
       (auto-book)  (deep link) (deep link) (phone/website)
             │
             v
       Booking History (SQLite)
             │
             v
       Google Calendar (via gog CLI)
```

## Setup

```bash
# Install
python3 -m pip install .

# Configure Google Places API key (required)
oakley-bookings setup --google-key YOUR_KEY

# Optional: Resy credentials for automated booking
oakley-bookings setup --resy-key KEY --resy-token TOKEN

# Verify
oakley-bookings status
```

## Commands

| Command | Description |
|---------|-------------|
| `setup` | Configure API keys |
| `status` | Check API connectivity and booking stats |
| `search` | Find restaurants by cuisine, area, or name |
| `details` | Full restaurant info with reviews |
| `check` | Check table availability |
| `book` | Book a table (preview by default, `--confirm` to execute) |
| `bookings` | List upcoming/past bookings |
| `cancel` | Cancel a booking |
| `modify` | Change date, time, or party size |
| `rate` | Rate a restaurant visit (1-5) |
| `remind` | Upcoming booking reminders (cron) |
| `rate-prompt` | Prompt for ratings on past visits (cron) |
| `suggest` | Restaurant suggestions based on history |

## Examples

```bash
# Search for Italian restaurants in Surry Hills
oakley-bookings search --query "Italian Surry Hills" --party-size 2

# Search near current location
oakley-bookings search --query "sushi" --near-me

# Check availability
oakley-bookings check --place-id ChIJ... --date 2026-02-20 --time 19:30 --party-size 2

# Preview a booking
oakley-bookings book --place-id ChIJ... --date 2026-02-20 --time 19:30 --party-size 2

# Confirm the booking
oakley-bookings book --place-id ChIJ... --date 2026-02-20 --time 19:30 --party-size 2 --confirm

# List upcoming bookings
oakley-bookings bookings --upcoming

# Rate a visit
oakley-bookings rate --booking-id BK_... --rating 5 --notes "incredible pasta"
```

## Cron Jobs

```cron
# Booking reminders — every 30 minutes
*/30 * * * * oakley-bookings remind

# Rating prompts — daily at 10am
0 10 * * * oakley-bookings rate-prompt
```

## Google APIs Required

Enable these in the same Google Cloud project (single API key covers both):

- **Places API (New)** — restaurant search and details
- **Geolocation API** — `--near-me` location detection

## Dependencies

- `requests>=2.28.0` — HTTP client for Google Places, Geolocation, and Resy APIs
- `pytz>=2023.3` — Sydney timezone handling
- `gog` CLI (system) — Google Calendar integration (optional, for calendar entries after booking)

## Data

Runtime data stored at `~/.oakley-bookings/data/`:

- `bookings.db` — SQLite database (bookings, restaurants, ratings, preferences)
- `cache/` — API response cache (1hr search, 24hr details, 5min availability)
- `config.json` — API credentials

Override with `OAKLEY_BOOKINGS_DATA_DIR` env var.

## Platform Support

| Platform | Discovery | Booking | Notes |
|----------|-----------|---------|-------|
| Resy | API search | Automated | Full booking flow via API |
| OpenTable | URL detection | Deep link | Pre-filled booking link |
| Quandoo | URL detection | Deep link | Pre-filled booking link |
| Phone/other | Google Places | Manual | Phone number provided |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

68 unit tests covering formatting, platform detection, deep links, DB CRUD, Places response parsing, and discovery ranking.
