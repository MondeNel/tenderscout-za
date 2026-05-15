# Windows event loop fix — must be before any asyncio imports
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import models
from database import engine, check_db_connection, SessionLocal
from routers import auth, credits, search, tenders, user, admin
from routers.proxy import router as proxy_router
from scraper.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

API_TITLE   = "TenderScout ZA"
API_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(f"  {API_TITLE} v{API_VERSION} starting")
    logger.info(f"  CORS origins: {ALLOWED_ORIGINS}")
    logger.info("=" * 60)

    if not check_db_connection():
        logger.critical("[INIT] Cannot connect to database — aborting")
        raise SystemExit(1)

    try:
        models.Base.metadata.create_all(bind=engine)
        logger.info("[INIT] Database tables verified")
    except Exception as e:
        logger.critical(f"[INIT] Failed to create tables: {e}")
        raise SystemExit(1)

    try:
        with SessionLocal() as db:
            total  = db.query(models.Tender).count()
            active = db.query(models.Tender).filter(models.Tender.is_active).count()
            logger.info(f"[INIT] Tenders: {total} total, {active} active")
    except Exception as e:
        logger.warning(f"[INIT] Could not read DB stats: {e}")

    try:
        start_scheduler()
        logger.info("[INIT] Scheduler started")
    except Exception as e:
        logger.error(f"[INIT] Scheduler failed to start (manual trigger available): {e}")

    logger.info(f"[INIT] ✅ {API_TITLE} ready")
    yield

    logger.info(f"[SHUTDOWN] Stopping {API_TITLE}...")
    stop_scheduler()
    logger.info("[SHUTDOWN] ✅ Done")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Exception handlers
# FastAPI's built-in handlers bypass CORSMiddleware, so we inject headers
# manually to prevent spurious CORS errors on 401/422 responses.
# ---------------------------------------------------------------------------

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
        content={"error": exc.detail, "status": exc.status_code, "timestamp": _now()},
        headers=_cors_headers(request),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation Error", "detail": exc.errors(), "timestamp": _now()},
        headers=_cors_headers(request),
    )

# ---------------------------------------------------------------------------
# Routers — prefixes are defined inside each router
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(tenders.router)
app.include_router(search.router)
app.include_router(credits.router)
app.include_router(user.router)
app.include_router(admin.router)   # was inline in main.py
app.include_router(proxy_router)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health_check():
    try:
        with SessionLocal() as db:
            total  = db.query(models.Tender).count()
            active = db.query(models.Tender).filter(models.Tender.is_active).count()
        return {"status": "healthy", "db_connected": True,
                "total_tenders": total, "active_tenders": active, "timestamp": _now()}
    except Exception as e:
        logger.error(f"[HEALTH] {e}")
        return JSONResponse(status_code=503, content={
            "status": "unhealthy", "db_connected": False, "error": str(e), "timestamp": _now(),
        })

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("RELOAD", "false").lower() == "true",
        log_level="info",
    )