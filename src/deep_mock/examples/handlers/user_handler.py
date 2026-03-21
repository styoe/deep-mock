"""User handler that uses services."""

from deep_mock.examples.services.database import fetch_user, DatabaseClient
from deep_mock.examples.services.external_api import get_user_profile


def handle_user_request(user_id: str) -> dict:
    """Handle a user request."""
    profile = get_user_profile(user_id)
    return {
        "status": "success",
        "profile": profile,
    }


def handle_direct_fetch(user_id: str) -> dict:
    """Directly fetch user from database."""
    user = fetch_user(user_id)
    return {"status": "success", "user": user}
