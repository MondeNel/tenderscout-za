#!/usr/bin/env python
"""
scripts/create_db.py — Database Table Creation Utility
========================================================
Create (or initialise) all database tables defined in `models.py`.

Usage:
    cd backend
    python scripts/create_db.py

This script is idempotent: if tables already exist they are left untouched
(SQLAlchemy's `create_all` uses `CREATE TABLE IF NOT EXISTS` semantics).

It is safe to run at any time to ensure the schema matches the current
model definitions, e.g., after adding new tables or columns.
"""

import sys
import os

# ---------------------------------------------------------------------------
# Ensure the `backend/` directory is on sys.path so we can import our
# project modules (database, models, etc.) regardless of where the script
# is invoked from.
# ---------------------------------------------------------------------------
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from database import engine  # SQLAlchemy engine (configured in database.py)
import models                # All ORM models (must be imported so Base knows them)


def main() -> None:
    """Create all tables that don't already exist in the database."""
    print("🔨 Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    print("✅ Database created successfully with all tables!")
    print("")
    print("Tables created:")
    for table in models.Base.metadata.sorted_tables:
        print(f"  - {table.name}")


if __name__ == "__main__":
    main()