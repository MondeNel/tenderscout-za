# Windows event loop fix — MUST be before any other imports that touch asyncio
# On Windows, the default ProactorEventLoop can cause issues with subprocess
# and networking; switching to SelectorEventLoop prevents hangs.
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session

import models
import auth_utils
from database import engine, get_db, check_db_connection
from routers import auth, credits, search, tenders, user
from routers.proxy import router as proxy_router
from scraper.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

# ------------------------------------------------------------------
# Logging setup – shared across the whole application.
# We keep the root logger at INFO and suppress noisy third-party
# loggers to avoid terminal spam (especially from httpx/httpcore).
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Silence the HTTP request/response logs from httpx and httpcore,
# which would otherwise print every single URL the scraper fetches.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
# APScheduler can be verbose at INFO level — quiet it down.
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# CORS – allowed origins are read from the environment so that
# development and production can have different frontend URLs.
# ------------------------------------------------------------------
ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

API_VERSION = "1.0.0"
API_TITLE   = "TenderScout ZA"


# ------------------------------------------------------------------
# Application lifespan – run startup/shutdown logic.
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
    1. Check the database connection.
    2. Create/verify all database tables.
    3. Print a summary of existing tenders and scraper sources.
    4. Start the APScheduler (which may kick off an immediate scrape).

    Shutdown:
    1. Gracefully stop the scheduler.
    """
    logger.info("=" * 60)
    logger.info(f"  {API_TITLE} v{API_VERSION} starting up")
    logger.info(f"  CORS origins: {ALLOWED_ORIGINS}")
    logger.info("=" * 60)

    # ---------- Database health check ----------
    if not check_db_connection():
        logger.critical("[INIT] Cannot connect to database — aborting startup")
        raise SystemExit(1)

    # ---------- Auto-create / verify tables ----------
    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("[INIT] Database tables verified")
    except Exception as e:
        logger.critical(f"[INIT] Failed to create tables: {e}")
        raise SystemExit(1)

    # ---------- Print current DB stats ----------
    db = None
    try:
        from database import SessionLocal
        db = SessionLocal()
        total   = db.query(models.Tender).count()
        active  = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        sources = db.query(models.ScraperStatus).count()
        logger.info(f"[INIT] Tenders: {total} total, {active} active, {sources} scraper sources")
    except Exception as e:
        logger.warning(f"[INIT] Could not read DB stats: {e}")
    finally:
        if db:
            db.close()

    # ---------- Start the scheduler ----------
    try:
        start_scheduler()
        logger.info("[INIT] Scraper scheduler started")
    except Exception as e:
        logger.error(f"[INIT] Scheduler failed to start: {e}")

    logger.info(f"[INIT] ✅ {API_TITLE} ready")
    yield  # <-- application runs here

    # ---------- Shutdown ----------
    logger.info(f"[SHUTDOWN] Stopping {API_TITLE}...")
    stop_scheduler()
    logger.info("[SHUTDOWN] ✅ Done")


# ------------------------------------------------------------------
# FastAPI app instance
# ------------------------------------------------------------------
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc alternative
)

# ------------------------------------------------------------------
# CORS middleware – must be added before any routes.
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,   # cookies / auth headers
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def _cors_headers(request: Request) -> dict:
    """
    Helper that returns the appropriate CORS headers for a response
    only if the request's Origin is in the allowed list.
    """
    origin = request.headers.get("origin", "")
    if origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin":      origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary":                             "Origin",
        }
    return {}


# ------------------------------------------------------------------
# Custom exception handlers – ensure error responses also carry CORS
# headers, so the frontend can read the error body.
# ------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Catch any HTTPException raised in the app and return a consistent
    JSON error response with CORS headers.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error":     exc.detail,
            "status":    exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Catch Pydantic validation errors and return a 422 with CORS headers.
    """
    return JSONResponse(
        status_code=422,
        content={
            "error":     "Validation Error",
            "detail":    exc.errors(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=_cors_headers(request),
    )


# ------------------------------------------------------------------
# Include routers – each router groups related endpoints.
# ------------------------------------------------------------------
app.include_router(auth.router)       # /auth/*
app.include_router(tenders.router)    # /tenders/*
app.include_router(search.router)     # /search/*
app.include_router(credits.router)    # /credits/*
app.include_router(user.router)       # /user/*
app.include_router(proxy_router)      # /proxy/*


# ------------------------------------------------------------------
# Health check – used by load balancers or monitoring.
# ------------------------------------------------------------------
@app.get("/health", tags=["system"])
def health_check():
    """
    Return a JSON payload with system status and database stats.
    If the DB is unreachable, returns 503 instead of 200.
    """
    db = None
    try:
        from database import SessionLocal
        db = SessionLocal()
        total  = db.query(models.Tender).count()
        active = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        return {
            "status":         "healthy",
            "db_connected":   True,
            "total_tenders":  total,
            "active_tenders": active,
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"[HEALTH] DB check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status":       "unhealthy",
                "db_connected": False,
                "error":        str(e),
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            },
        )
    finally:
        if db:
            db.close()


# ------------------------------------------------------------------
# Admin endpoints (protected by get_current_user dependency)
# ------------------------------------------------------------------
@app.get("/admin/scraper-status", tags=["admin"])
def scraper_status(
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return a list of all scraper sources, ordered by last scrape time,
    with their health status, result counts, and last error.
    """
    rows = (
        db.query(models.ScraperStatus)
        .order_by(models.ScraperStatus.last_scraped_at.desc())
        .all()
    )
    return [
        {
            "site":         r.site_name,
            "last_scraped": r.last_scraped_at.isoformat() if r.last_scraped_at else None,
            "result_count": r.last_result_count,
            "is_healthy":   r.is_healthy,
            "last_error":   r.last_error,
        }
        for r in rows
    ]


@app.post("/admin/trigger-scrape", tags=["admin"])
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    current_user:     models.User = Depends(auth_utils.get_current_user),
):
    """
    Manually trigger a full scraping cycle.

    The scraping runs in the background (via BackgroundTasks) so the
    API responds immediately. The user receives a 200 response and the
    scrape continues asynchronously.
    """
    from scraper.engine import run_scraper
    background_tasks.add_task(run_scraper)
    logger.info(f"[ADMIN] Scrape triggered by user={current_user.id}")
    return {
        "message":   "Scraper triggered in background",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/admin/scheduler-status", tags=["admin"])
def scheduler_status(
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Return detailed scheduler status – whether it's running, when the
    last scrape ran, and the configured schedule.
    """
    return get_scheduler_status()


# ------------------------------------------------------------------
# Run the server directly (for development)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),  # listen on all interfaces
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("RELOAD", "false").lower() == "true",
        log_level="info",
    )