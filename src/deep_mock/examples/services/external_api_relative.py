"""External API service using relative imports."""

from .database import fetch_user, connect_to_database


def get_user_profile_relative(user_id: str) -> dict:
    """Get user profile using relative imports."""
    connection = connect_to_database("localhost")
    user = fetch_user(user_id)
    return {
        "user": user,
        "connection": connection,
        "enriched": True,
        "import_type": "relative",
    }


def get_user_name_relative(user_id: str) -> str:
    """Get just the user's name using relative imports."""
    user = fetch_user(user_id)
    return user["name"]
