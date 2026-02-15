"""SQLite database — bookings, restaurants, ratings, preferences."""

from __future__ import annotations

import sqlite3
from typing import Optional

from oakley_bookings.common.config import Config

_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    """Get or create a SQLite connection with WAL mode."""
    global _conn
    if _conn is not None:
        return _conn

    Config.ensure_dirs()
    _conn = sqlite3.connect(str(Config.db_path), timeout=10)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bookings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id      TEXT UNIQUE NOT NULL,
            restaurant_name TEXT NOT NULL,
            restaurant_addr TEXT,
            place_id        TEXT,
            date            TEXT NOT NULL,
            time            TEXT NOT NULL,
            party_size      INTEGER NOT NULL,
            platform        TEXT NOT NULL,
            platform_ref    TEXT,
            status          TEXT NOT NULL DEFAULT 'confirmed',
            google_maps_url TEXT,
            phone           TEXT,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS restaurants (
            place_id        TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            address         TEXT,
            lat             REAL,
            lng             REAL,
            rating          REAL,
            review_count    INTEGER,
            price_level     TEXT,
            phone           TEXT,
            website         TEXT,
            google_maps_url TEXT,
            platform        TEXT,
            platform_id     TEXT,
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id      TEXT REFERENCES bookings(booking_id),
            rating          INTEGER NOT NULL,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS preferences (
            key             TEXT PRIMARY KEY,
            value           TEXT NOT NULL,
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date);
        CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);
        CREATE INDEX IF NOT EXISTS idx_bookings_place_id ON bookings(place_id);
    """)


# ─── Booking CRUD ─────────────────────────────────────────────────────────────

def save_booking(booking: dict) -> int:
    """Insert a new booking record. Returns the row id."""
    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO bookings (
            booking_id, restaurant_name, restaurant_addr, place_id,
            date, time, party_size, platform, platform_ref, status,
            google_maps_url, phone, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            booking["booking_id"],
            booking["restaurant_name"],
            booking.get("restaurant_addr", ""),
            booking.get("place_id", ""),
            booking["date"],
            booking["time"],
            booking["party_size"],
            booking["platform"],
            booking.get("platform_ref"),
            booking.get("status", "confirmed"),
            booking.get("google_maps_url", ""),
            booking.get("phone", ""),
            booking.get("notes", ""),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_booking(booking_id: str) -> Optional[dict]:
    """Get a booking by its booking_id."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ? LIMIT 1",
        (booking_id,),
    ).fetchone()
    return dict(row) if row else None


def list_bookings(
    status: Optional[str] = None,
    upcoming: bool = False,
    past: bool = False,
    limit: int = 20,
) -> list[dict]:
    """List bookings with optional filters."""
    conn = _get_conn()
    sql = "SELECT * FROM bookings WHERE 1=1"
    params: list = []

    if status:
        sql += " AND status = ?"
        params.append(status)

    if upcoming:
        sql += " AND date >= date('now') AND status IN ('confirmed', 'modified')"

    if past:
        sql += " AND date < date('now')"

    sql += " ORDER BY date ASC, time ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_booking_status(booking_id: str, status: str, **kwargs) -> bool:
    """Update a booking's status and optional fields."""
    conn = _get_conn()
    sets = ["status = ?", "updated_at = datetime('now')"]
    values = [status]

    allowed = {"date", "time", "party_size", "platform_ref", "notes"}
    for key, val in kwargs.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(val)

    values.append(booking_id)
    sql = f"UPDATE bookings SET {', '.join(sets)} WHERE booking_id = ?"
    cursor = conn.execute(sql, values)
    conn.commit()
    return cursor.rowcount > 0


# ─── Restaurant CRUD ──────────────────────────────────────────────────────────

def save_restaurant(restaurant: dict) -> None:
    """Upsert a restaurant record."""
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO restaurants (
            place_id, name, address, lat, lng, rating, review_count,
            price_level, phone, website, google_maps_url, platform,
            platform_id, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            restaurant["place_id"],
            restaurant["name"],
            restaurant.get("address", ""),
            restaurant.get("lat"),
            restaurant.get("lng"),
            restaurant.get("rating"),
            restaurant.get("review_count"),
            restaurant.get("price_level"),
            restaurant.get("phone", ""),
            restaurant.get("website", ""),
            restaurant.get("google_maps_url", ""),
            restaurant.get("platform"),
            restaurant.get("platform_id"),
        ),
    )
    conn.commit()


def get_restaurant(place_id: str) -> Optional[dict]:
    """Get a cached restaurant by place_id."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM restaurants WHERE place_id = ? LIMIT 1",
        (place_id,),
    ).fetchone()
    return dict(row) if row else None


# ─── Ratings ──────────────────────────────────────────────────────────────────

def save_rating(booking_id: str, rating: int, notes: Optional[str] = None) -> int:
    """Save a rating for a completed booking."""
    conn = _get_conn()

    # Mark booking as completed
    update_booking_status(booking_id, "completed")

    cursor = conn.execute(
        "INSERT INTO ratings (booking_id, rating, notes) VALUES (?, ?, ?)",
        (booking_id, rating, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_ratings(place_id: Optional[str] = None) -> list[dict]:
    """Get ratings, optionally filtered by place_id."""
    conn = _get_conn()
    if place_id:
        rows = conn.execute(
            """SELECT r.*, b.restaurant_name, b.place_id, b.date
               FROM ratings r JOIN bookings b ON r.booking_id = b.booking_id
               WHERE b.place_id = ? ORDER BY r.created_at DESC""",
            (place_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT r.*, b.restaurant_name, b.place_id, b.date
               FROM ratings r JOIN bookings b ON r.booking_id = b.booking_id
               ORDER BY r.created_at DESC""",
        ).fetchall()
    return [dict(r) for r in rows]


def get_unrated_past_bookings() -> list[dict]:
    """Get confirmed bookings from yesterday without ratings (for rate-prompt)."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT b.* FROM bookings b
           LEFT JOIN ratings r ON b.booking_id = r.booking_id
           WHERE b.date = date('now', '-1 day')
             AND b.status = 'confirmed'
             AND r.id IS NULL
           ORDER BY b.time ASC""",
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Preferences ──────────────────────────────────────────────────────────────

def get_preferences() -> dict:
    """Get all preference key-value pairs."""
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM preferences ORDER BY key").fetchall()
    return {r[0]: r[1] for r in rows}


def update_preference(key: str, value: str) -> None:
    """Set a preference (upsert)."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, datetime('now'))",
        (key, value),
    )
    conn.commit()


# ─── Stats helpers ────────────────────────────────────────────────────────────

def count_bookings(status: Optional[str] = None) -> int:
    conn = _get_conn()
    if status:
        row = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = ?", (status,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()
    return row[0]


def get_top_restaurants(limit: int = 5) -> list[dict]:
    """Get most-visited restaurants with average ratings."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT b.restaurant_name, b.place_id, COUNT(*) as visit_count,
                  AVG(r.rating) as avg_rating
           FROM bookings b
           LEFT JOIN ratings r ON b.booking_id = r.booking_id
           GROUP BY b.place_id
           ORDER BY visit_count DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
