import pytest
from sqlalchemy import text
from app.db.connection import engine


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_db: skip when PostgreSQL is unavailable")


def pg_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


_pg_up = pg_available()


def pytest_collection_modifyitems(config, items):
    skip_db = pytest.mark.skip(reason="PostgreSQL unavailable")
    for item in items:
        if "requires_db" in item.keywords and not _pg_up:
            item.add_marker(skip_db)
