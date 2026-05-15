# Windows event loop fix — MUST be before any other imports that touch asyncio
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# --- Silence noisy third‑party loggers ---
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in
    os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

API_VERSION = "1.0.0"
API_TITLE   = "TenderScout ZA"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(f"  {API_TITLE} v{API_VERSION} starting up")
    logger.info(f"  CORS origins: {ALLOWED_ORIGINS}")
    logger.info("=" * 60)

    if not check_db_connection():
        logger.critical("[INIT] Cannot connect to database — aborting startup")
        raise SystemExit(1)

    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("[INIT] Database tables verified")
    except Exception as e:
        logger.critical(f"[INIT] Failed to create tables: {e}")
        raise SystemExit(1)

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

    try:
        start_scheduler()
        logger.info("[INIT] Scraper scheduler started")
    except Exception as e:
        logger.error(f"[INIT] Scheduler failed to start: {e}")

    logger.info(f"[INIT] ✅ {API_TITLE} ready")
    yield
    logger.info(f"[SHUTDOWN] Stopping {API_TITLE}...")
    stop_scheduler()
    logger.info("[SHUTDOWN] ✅ Done")

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

def _cors_headers(request: Request) -> dict:
    origin = request.headers.get("origin", "")
    if origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin":      origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary":                             "Origin",
        }
    return {}

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
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
    return JSONResponse(
        status_code=422,
        content={
            "error":     "Validation Error",
            "detail":    exc.errors(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=_cors_headers(request),
    )

app.include_router(auth.router)
app.include_router(tenders.router)
app.include_router(search.router)
app.include_router(credits.router)
app.include_router(user.router)
app.include_router(proxy_router)

@app.get("/health", tags=["system"])
def health_check():
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

@app.get("/admin/scraper-status", tags=["admin"])
def scraper_status(
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
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
    return get_scheduler_status()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("RELOAD", "false").lower() == "true",
        log_level="info",
    )