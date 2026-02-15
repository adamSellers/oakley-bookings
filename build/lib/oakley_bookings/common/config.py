import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("OAKLEY_BOOKINGS_DATA_DIR", Path.home() / ".oakley-bookings" / "data"))
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "bookings.db"
CONFIG_PATH = DATA_DIR / "config.json"

CACHE_TTL = {
    "search": 3600,        # 1 hour — restaurant search results
    "details": 86400,      # 24 hours — restaurant details
    "availability": 300,   # 5 minutes — time slot availability
}

STALE_CACHE_MAX_AGE = 86400  # 24 hours fallback

# Rate limits
GOOGLE_RATE_LIMIT_CALLS = 10
GOOGLE_RATE_LIMIT_PERIOD = 1  # 10 req/sec

RESY_RATE_LIMIT_CALLS = 5
RESY_RATE_LIMIT_PERIOD = 1  # 5 req/sec

TELEGRAM_MAX_LENGTH = 4096

TIMEZONE = "Australia/Sydney"

REQUEST_TIMEOUT = 10  # seconds

# Discovery defaults
DEFAULT_LAT = -33.8688        # Sydney CBD
DEFAULT_LNG = 151.2093
DEFAULT_RADIUS_M = 5000       # 5km
DEFAULT_PARTY_SIZE = 2
DEFAULT_RATING_MIN = 4.0

# Google Places API (New)
GOOGLE_PLACES_BASE_URL = "https://places.googleapis.com/v1"

# Resy API
RESY_BASE_URL = "https://api.resy.com"


class Config:
    """Central access point for all configuration."""

    package_dir = _PACKAGE_DIR
    data_dir = DATA_DIR
    cache_dir = CACHE_DIR
    db_path = DB_PATH
    config_path = CONFIG_PATH

    cache_ttl = CACHE_TTL
    stale_cache_max_age = STALE_CACHE_MAX_AGE

    google_rate_limit_calls = GOOGLE_RATE_LIMIT_CALLS
    google_rate_limit_period = GOOGLE_RATE_LIMIT_PERIOD
    resy_rate_limit_calls = RESY_RATE_LIMIT_CALLS
    resy_rate_limit_period = RESY_RATE_LIMIT_PERIOD

    telegram_max_length = TELEGRAM_MAX_LENGTH
    timezone = TIMEZONE
    request_timeout = REQUEST_TIMEOUT

    default_lat = DEFAULT_LAT
    default_lng = DEFAULT_LNG
    default_radius_m = DEFAULT_RADIUS_M
    default_party_size = DEFAULT_PARTY_SIZE
    default_rating_min = DEFAULT_RATING_MIN

    google_places_base_url = GOOGLE_PLACES_BASE_URL
    resy_base_url = RESY_BASE_URL

    @classmethod
    def ensure_dirs(cls):
        cls.data_dir.mkdir(parents=True, exist_ok=True)
        cls.cache_dir.mkdir(parents=True, exist_ok=True)
