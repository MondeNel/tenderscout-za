import sys
import asyncio
import logging
import os
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session

# Local imports
import models
from database import engine, SessionLocal, get_db
from routers import auth, credits, search, tenders, user
from routers.proxy import router as proxy_router
from scraper.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

# Fix for Windows event loop policy with Playwright/Asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")]

API_VERSION = "1.0.0"
API_TITLE = "TenderScout ZA"

# =============================================================================
# APPLICATION LIFESPAN
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"--- Starting {API_TITLE} v{API_VERSION} ---")
    
    # 1. Database Initialization
    try:
        # Note: In production with Alembic, you might skip create_all
        models.Base.metadata.create_all(bind=engine)
        logger.info("[INIT] Database tables verified/created")
    except Exception as e:
        logger.critical(f"[INIT] Database connection failed: {e}")
        raise SystemExit(1)

    # 2. Start Scheduler
    try:
        start_scheduler()
        logger.info("[INIT] Scraper scheduler active")
    except Exception as e:
        logger.error(f"[INIT] Scheduler failed: {e}")

    yield

    # 3. Shutdown
    logger.info("--- Shutting down TenderScout ZA ---")
    stop_scheduler()

# =============================================================================
# FASTAPI APPLICATION
# =============================================================================
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# =============================================================================
# ERROR HANDLERS (With CORS Injection)
# =============================================================================
def _get_cors_headers(request: Request) -> dict:
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"}
    return {"Access-Control-Allow-Origin": ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"}

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status": exc.status_code},
        headers=_get_cors_headers(request)
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation Error", "detail": exc.errors()},
        headers=_get_cors_headers(request)
    )

# =============================================================================
# ROUTERS
# =============================================================================
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tenders.router, prefix="/api/tenders", tags=["tenders"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(credits.router, prefix="/api/credits", tags=["billing"])
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(proxy_router, prefix="/api/proxy", tags=["utils"])

# =============================================================================
# SYSTEM ENDPOINTS
# =============================================================================
@app.get("/health", tags=["system"])
async def health_check(db: Session = Depends(get_db)):
    """Health check optimized to use dependency injection and async-safe DB calls."""
    try:
        # Use simple count for quick health verification
        count = db.query(models.Tender).limit(1).count()
        return {
            "status": "healthy",
            "db_connected": True,
            "tender_sample": count,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=503, content={"status": "unhealthy", "db": "disconnected"})

@app.get("/admin/scraper-status", tags=["admin"])
async def scraper_status(db: Session = Depends(get_db)):
    rows = db.query(models.ScraperStatus).order_by(models.ScraperStatus.last_scraped_at.desc()).all()
    return rows

@app.post("/admin/trigger-scrape", tags=["admin"])
async def trigger_scrape(background_tasks: BackgroundTasks):
    from scraper.engine import run_scraper
    background_tasks.add_task(run_scraper)
    return {"message": "Scraper triggered in background"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)