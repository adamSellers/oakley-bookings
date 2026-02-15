"""Credential management — Google Places API key + Resy auth tokens."""

from __future__ import annotations

import json
from typing import Optional

from oakley_bookings.common.config import Config


def _load_config() -> dict:
    """Load config from disk."""
    Config.ensure_dirs()
    if not Config.config_path.exists():
        return {}
    try:
        return json.loads(Config.config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_config(data: dict) -> None:
    """Write config to disk."""
    Config.ensure_dirs()
    Config.config_path.write_text(json.dumps(data, indent=2))


# ─── Google Places ────────────────────────────────────────────────────────────

def save_google_key(api_key: str) -> None:
    """Save Google Places API key."""
    config = _load_config()
    config["google_places_api_key"] = api_key
    _save_config(config)


def get_google_key() -> Optional[str]:
    """Return Google Places API key or None."""
    config = _load_config()
    return config.get("google_places_api_key") or None


def has_google_key() -> bool:
    return get_google_key() is not None


# ─── Resy ─────────────────────────────────────────────────────────────────────

def save_resy_credentials(api_key: str, auth_token: str) -> None:
    """Save Resy API key and auth token."""
    config = _load_config()
    config["resy_api_key"] = api_key
    config["resy_auth_token"] = auth_token
    _save_config(config)


def get_resy_credentials() -> Optional[tuple[str, str]]:
    """Return (api_key, auth_token) or None if not configured."""
    config = _load_config()
    key = config.get("resy_api_key")
    token = config.get("resy_auth_token")
    if key and token:
        return (key, token)
    return None


def has_resy_credentials() -> bool:
    return get_resy_credentials() is not None
