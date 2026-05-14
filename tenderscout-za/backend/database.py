from sqlalchemy import create_engine, event, text, MetaData
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv
import logging
import os

load_dotenv()

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tenderscout.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Define naming conventions for constraints to ensure smooth Alembic migrations
# This prevents "Constraint name is too long" or "Unnamed constraint" errors in Postgres.
POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# =============================================================================
# ENGINE CONFIGURATION
# =============================================================================

if IS_SQLITE:
    # check_same_thread=False is vital for FastAPI+SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

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
        pool_size=int(os.getenv("DB_POOL_SIZE", 20)), # Increased default for production
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

# =============================================================================
# SESSION & BASE
# =============================================================================

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    # Apply naming convention to the metadata
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)

# =============================================================================
# UTILITIES & DEPENDENCIES
# =============================================================================

def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"[DB] Connectivity check failed: {e}")
        return False

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # Log the error for observability
        logger.error(f"[DB] Session transaction error: {e}")
        db.rollback()
        raise
    finally:
        db.close()