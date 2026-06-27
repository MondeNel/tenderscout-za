"""
database.py — Database Engine & Session Configuration
======================================================
Creates the SQLAlchemy engine and session factory, with separate
configurations for SQLite (development) and PostgreSQL (production).

Also provides:
- check_db_connection(): health‑check helper.
- get_db(): FastAPI dependency that yields a database session.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import logging
import os

# Load environment variables from a .env file (if present)
load_dotenv()

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Database URL – defaults to a local SQLite file for easy development.
# In production, set DATABASE_URL to a PostgreSQL connection string.
# ------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tenderscout.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# ------------------------------------------------------------------
# SQLite configuration – tuned for concurrent reads under WAL mode.
# ------------------------------------------------------------------
if IS_SQLITE:
    # `check_same_thread=False` is required because FastAPI's threaded
    # request handlers share a single SQLite connection.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

    # Apply SQLite pragmas on every new connection:
    # - WAL mode allows concurrent reads without blocking writes.
    # - NORMAL synchronous reduces disk I/O while still being safe
    #   for WAL.
    # - Foreign keys are enforced at the database level.
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ------------------------------------------------------------------
# PostgreSQL / production configuration – connection pooling.
# ------------------------------------------------------------------
else:
    engine = create_engine(
        DATABASE_URL,
        # Base pool size (number of permanent connections)
        pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
        # Extra connections allowed when the pool is full
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 20)),
        # Verify connections are still alive before using them
        pool_pre_ping=True,
        # Recycle connections after 30 minutes to avoid stale sessions
        pool_recycle=1800,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

# ------------------------------------------------------------------
# Session factory – `autocommit=False` and `autoflush=False` give us
# explicit control over transactions, which is essential for credit
# operations and the scraping pipeline.
# ------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Declarative base for all ORM models
class Base(DeclarativeBase):
    pass


def check_db_connection() -> bool:
    """
    Execute a lightweight query to verify the database is reachable.

    Returns True on success, False otherwise (with an error log).
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[DB] Connection healthy")
        return True
    except Exception as e:
        logger.error(f"[DB] Connection failed: {e}")
        return False


def get_db():
    """
    FastAPI dependency that yields a SQLAlchemy session.

    The session is automatically:
    - rolled back on any exception.
    - closed after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()