"""
General utility functions used across the application.
"""

from typing import Any, Dict
from datetime import datetime


def now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.utcnow().isoformat() + "Z"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float safely with default fallback."""
    try:
        return float(value)
    except Exception:
        return default



