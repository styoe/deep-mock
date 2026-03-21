"""External API service that uses the database module."""

from deep_mock.examples.services.database import fetch_user, connect_to_database


def get_user_profile(user_id: str) -> dict:
    """Get user profile by combining database data."""
    connection = connect_to_database("localhost")
    user = fetch_user(user_id)
    return {
        "user": user,
        "connection": connection,
        "enriched": True,
    }


def get_user_name(user_id: str) -> str:
    """Get just the user's name."""
    user = fetch_user(user_id)
    return user["name"]
