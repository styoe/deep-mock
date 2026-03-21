"""Cache service with import-time initialization."""

from .database import fetch_user

# This runs ONCE at import time - fetches the system user
SYSTEM_USER = fetch_user("system")


def get_system_user() -> dict:
    """Return the cached system user."""
    return SYSTEM_USER


def get_system_user_name() -> str:
    """Return the cached system user's name."""
    return SYSTEM_USER["name"]
