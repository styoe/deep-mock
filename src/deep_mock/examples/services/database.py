"""Database service module."""


def connect_to_database(host: str, port: int = 5432) -> dict:
    """Connect to a real database (simulated)."""
    return {
        "connected": True,
        "host": host,
        "port": port,
        "connection_id": "real-connection-123",
    }


def fetch_user(user_id: str) -> dict:
    """Fetch user from database."""
    return {
        "id": user_id,
        "name": "Real User",
        "source": "database",
    }


class DatabaseClient:
    """A database client class."""

    def __init__(self, host: str):
        self.host = host
        self.connected = False

    def connect(self):
        self.connected = True
        return {"status": "connected", "host": self.host}

    def query(self, sql: str):
        return {"sql": sql, "results": ["real_result_1", "real_result_2"]}
