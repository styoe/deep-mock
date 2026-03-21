"""User service with indirect dependency on database.fetch_user."""

from .cache import get_system_user


# Module-level state computed using cache module (indirect dependency)
# cache.get_system_user() internally uses database.fetch_user
SYSTEM_USER_NAME = get_system_user()["name"]


def get_greeting() -> str:
    """Return a greeting using the cached system user name."""
    return f"Hello, {SYSTEM_USER_NAME}!"
