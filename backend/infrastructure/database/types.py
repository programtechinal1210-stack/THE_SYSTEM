"""
Database-portable SQLAlchemy types.

The historical code imported PostgreSQL UUID / JSONB / ARRAY directly.
The Core now uses portable aliases so SQLite is the development database
without forcing business modules to know the database vendor.
"""

from sqlalchemy import Uuid, JSON

# Preserve historical constructor names used across current models.
UUID = Uuid
JSONB = JSON


def ARRAY(*_args, **_kwargs):
    """
    Portable replacement for the one historical ARRAY column in the Core.
    Values are stored as JSON arrays under SQLite.
    """
    return JSON()