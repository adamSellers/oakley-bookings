from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytz

from .config import Config

_tz = pytz.timezone(Config.timezone)


def now_aest() -> datetime:
    return datetime.now(_tz)


def format_datetime_aest(dt: Optional[datetime] = None, fmt: str = "%d %b %Y %H:%M AEST") -> str:
    if dt is None:
        dt = now_aest()
    elif dt.tzinfo is None:
        dt = _tz.localize(dt)
    return dt.strftime(fmt)


def format_section_header(title: str) -> str:
    return f"**{title}**"


def format_list_item(text: str, indent: int = 0) -> str:
    prefix = "  " * indent
    return f"{prefix}- {text}"


def format_rating(rating: Optional[float], review_count: Optional[int] = None) -> str:
    """Format a Google Places rating like '4.5/5 (1,234 reviews)'."""
    if rating is None:
        return "No rating"
    stars = round(rating * 2) / 2  # Round to nearest 0.5
    parts = [f"{stars}/5"]
    if review_count is not None:
        parts.append(f"({review_count:,} reviews)")
    return " ".join(parts)


def format_price_level(price_level: Optional[str]) -> str:
    """Format Google Places price level to dollar signs."""
    mapping = {
        "PRICE_LEVEL_FREE": "Free",
        "PRICE_LEVEL_INEXPENSIVE": "$",
        "PRICE_LEVEL_MODERATE": "$$",
        "PRICE_LEVEL_EXPENSIVE": "$$$",
        "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
    }
    if price_level is None:
        return "Price N/A"
    return mapping.get(price_level, price_level)


def truncate_for_telegram(text: str, max_length: int = Config.telegram_max_length) -> str:
    if len(text) <= max_length:
        return text
    truncated = text[: max_length - 30]
    last_newline = truncated.rfind("\n")
    if last_newline > max_length // 2:
        truncated = truncated[:last_newline]
    return truncated + "\n\n... (truncated)"
