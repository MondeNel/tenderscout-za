import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime

import models
from database import engine
from routers import auth, credits, search, tenders, user
from routers.proxy import router as proxy_router
from scraper.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Strip whitespace from each origin — a trailing space causes silent CORS failures
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8080"
).split(",")]

API_VERSION = "1.0.0"
API_TITLE = "TenderScout ZA"
API_DESCRIPTION = """
South African government tender search and aggregation platform.
"""

# =============================================================================
# APPLICATION LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[MAIN] ═══════════════════════════════════════════════════════")
    logger.info(f"[MAIN] Starting {API_TITLE} v{API_VERSION}")
    logger.info(f"[MAIN] Accepting CORS origins: {ALLOWED_ORIGINS}")
    logger.info("[MAIN] ═══════════════════════════════════════════════════════")

    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("[MAIN] Database tables ensured")
    except Exception as e:
        logger.error(f"[MAIN] ❌ Database init failed: {e}")
        raise

    try:
        start_scheduler()
        logger.info("[MAIN] Scraper scheduler started")
    except Exception as e:
        logger.error(f"[MAIN] ❌ Scheduler failed to start: {e}")
        raise

    from database import SessionLocal
    db = SessionLocal()
    try:
        total   = db.query(models.Tender).count()
        active  = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        sources = db.query(models.ScraperStatus).count()
        logger.info(f"[MAIN] DB: {total} tenders ({active} active) from {sources} sources")
    except Exception as e:
        logger.warning(f"[MAIN] Could not read initial DB stats: {e}")
    finally:
        db.close()

    logger.info("[MAIN] ✅ TenderScout ZA is ready to serve requests")

    yield

    logger.info("[MAIN] Shutting down...")
    stop_scheduler()
    logger.info("[MAIN] ✅ TenderScout ZA stopped")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# =============================================================================
# CORS MIDDLEWARE
# =============================================================================
# ⚠️  MUST be registered before any other middleware or auth logic.
#
# Root cause of the original CORS error:
#   Browser sends a preflight OPTIONS request → auth dependency runs first →
#   throws 401 → FastAPI returns the error with NO CORS headers →
#   browser blocks the actual request before it even fires.
#
# With CORSMiddleware registered first, OPTIONS requests are intercepted and
# answered with the correct headers before any route handler or dependency runs.

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# =============================================================================
# ROUTERS
# =============================================================================

app.include_router(auth.router)
app.include_router(credits.router)
app.include_router(search.router)
app.include_router(tenders.router)
app.include_router(user.router)
app.include_router(proxy_router)


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@app.get("/")
def root():
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    from database import SessionLocal
    db = SessionLocal()
    try:
        total  = db.query(models.Tender).count()
        active = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        return {
            "status": "healthy",
            "database": "connected",
            "total_tenders": total,
            "active_tenders": active,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[MAIN] Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
    finally:
        db.close()


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.get("/admin/scraper-status")
def scraper_status():
    from database import SessionLocal
    db = SessionLocal()
    try:
        rows = db.query(models.ScraperStatus).order_by(
            models.ScraperStatus.last_scraped_at.desc()
        ).all()
        return [
            {
                "site":         s.site_name,
                "last_scraped": s.last_scraped_at.isoformat() if s.last_scraped_at else None,
                "result_count": s.last_result_count,
                "is_healthy":   s.is_healthy,
                "last_error":   s.last_error,
            }
            for s in rows
        ]
    finally:
        db.close()


@app.post("/admin/trigger-scrape")
async def trigger_scrape(background_tasks: BackgroundTasks):
    from scraper.engine import run_scraper
    background_tasks.add_task(run_scraper)
    logger.info("[MAIN] Manual scraper run triggered via admin endpoint")
    return {
        "status": "scrape triggered",
        "message": "Scraper is running in the background.",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/admin/scheduler-status")
def scheduler_status():
    return get_scheduler_status()


# =============================================================================
# ERROR HANDLERS
# =============================================================================
# ⚠️  FastAPI's CORSMiddleware only attaches Access-Control-* headers to
# responses that flow through it normally. When an HTTPException is raised
# inside a route (401, 402, 422, etc.), FastAPI's built-in exception handler
# short-circuits and returns the response directly — bypassing the middleware
# stack — so no CORS headers are attached.
#
# The fix: override the global HTTPException handler so every error response
# manually injects the correct CORS headers. This covers 401 (bad token),
# 402 (insufficient credits), 422 (validation), and anything else.

def _cors_headers(request: Request) -> dict:
    """Return CORS headers matching the request's Origin, if allowed."""
    origin = request.headers.get("origin", "")
    allowed = origin if origin in ALLOWED_ORIGINS else (
        ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"
    )
    return {
        "Access-Control-Allow-Origin":      allowed,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods":     "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers":     "Authorization, Content-Type",
        "Vary":                             "Origin",
    }


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Catch ALL HTTP exceptions and re-attach CORS headers."""
    logger.warning(f"[MAIN] HTTP {exc.status_code} on {request.method} {request.url}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error":     exc.detail,
            "status":    exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Catch Pydantic validation errors (422) and attach CORS headers."""
    logger.warning(f"[MAIN] Validation error on {request.method} {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error":     "Validation Error",
            "detail":    exc.errors(),
            "timestamp": datetime.utcnow().isoformat(),
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"[MAIN] Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error":     "Internal Server Error",
            "message":   "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
        },
        headers=_cors_headers(request),
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    port   = int(os.getenv("PORT", "8000"))
    host   = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(f"[MAIN] Starting uvicorn server on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )