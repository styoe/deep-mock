"""User handler using relative imports."""

from ..services.database import fetch_user, DatabaseClient
from ..services.external_api_relative import get_user_profile_relative


def handle_user_request_relative(user_id: str) -> dict:
    """Handle a user request using relative imports."""
    profile = get_user_profile_relative(user_id)
    return {
        "status": "success",
        "profile": profile,
        "import_type": "relative",
    }


def handle_direct_fetch_relative(user_id: str) -> dict:
    """Directly fetch user from database using relative imports."""
    user = fetch_user(user_id)
    return {"status": "success", "user": user, "import_type": "relative"}
