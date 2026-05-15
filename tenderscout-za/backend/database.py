import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL + dialect detection
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tenderscout.db")
IS_SQLITE    = DATABASE_URL.startswith("sqlite")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")    # concurrent reads during writes
        cur.execute("PRAGMA synchronous=NORMAL")  # safe + faster than FULL
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 20)),
        pool_pre_ping=True,   # drop stale connections before use
        pool_recycle=1800,    # recycle every 30 min (prevents idle timeout errors)
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[DB] Connection healthy")
        return True
    except Exception as e:
        logger.error(f"[DB] Connection failed: {e}")
        return False

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db():
    """
    Yield a session per request. Always rolls back on error and closes on exit.

    Usage:
        def route(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()