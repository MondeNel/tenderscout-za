from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import logging
import os

load_dotenv()

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE URL
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tenderscout.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# =============================================================================
# ENGINE CONFIGURATION
# =============================================================================
# SQLite and PostgreSQL need different settings:
#
#   SQLite:
#     - check_same_thread=False   → allows use across FastAPI worker threads
#     - No connection pooling     → SQLite is file-based, pooling is irrelevant
#
#   PostgreSQL (production):
#     - pool_size=10              → keep 10 persistent connections open
#     - max_overflow=20           → allow 20 extra connections under heavy load
#     - pool_pre_ping=True        → test connections before use (handles dropped
#                                   connections from DB restarts or idle timeouts)
#     - pool_recycle=1800         → recycle connections every 30 mins to prevent
#                                   stale connection errors on long-running servers

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

    # Enable WAL mode for SQLite — allows concurrent reads during writes,
    # which is critical for FastAPI's async request handling
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 20)),
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

# =============================================================================
# SESSION FACTORY
# =============================================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# =============================================================================
# DECLARATIVE BASE
# =============================================================================
# Using the modern SQLAlchemy 2.x style.
# declarative_base() still works but is deprecated — DeclarativeBase is the
# recommended approach going forward.

class Base(DeclarativeBase):
    pass

# =============================================================================
# DATABASE HEALTH CHECK
# =============================================================================

def check_db_connection() -> bool:
    """
    Test database connectivity.
    Called during startup to fail fast if DB is unreachable.
    Returns True if connected, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[DB] Connection healthy")
        return True
    except Exception as e:
        logger.error(f"[DB] Connection failed: {e}")
        return False

# =============================================================================
# DEPENDENCY — FastAPI route dependency
# =============================================================================

def get_db():
    """
    Yield a database session for use in FastAPI route dependencies.

    Guarantees:
      - Session is always closed after the request, even on error
      - Rolls back any uncommitted transaction if an exception is raised
        (prevents dirty state from leaking between requests)

    Usage in routes:
      def my_route(db: Session = Depends(get_db)):
          ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()