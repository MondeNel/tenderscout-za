# MUST be first — fixes Windows ProactorEventLoop before uvicorn creates anything
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:5173,http://localhost:3000,http://localhost:8080"
).split(",")

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
    """
    Application lifespan manager.
    """
    # Startup
    logger.info("[MAIN] ═══════════════════════════════════════════════════════")
    logger.info(f"[MAIN] Starting {API_TITLE} v{API_VERSION}")
    logger.info("[MAIN] ═══════════════════════════════════════════════════════")
    
    # Ensure database tables exist
    models.Base.metadata.create_all(bind=engine)
    logger.info("[MAIN] Database tables ensured")
    
    # Start the scraper scheduler
    start_scheduler()
    logger.info("[MAIN] Scraper scheduler started")
    
    # Log initial database stats
    from database import SessionLocal
    db = SessionLocal()
    try:
        total = db.query(models.Tender).count()
        active = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        sources = db.query(models.ScraperStatus).count()
        logger.info(f"[MAIN] Database contains {total} tenders ({active} active) from {sources} sources")
    finally:
        db.close()
    
    logger.info("[MAIN] ✅ TenderScout ZA is ready to serve requests")
    
    yield  # Application runs here
    
    # Shutdown
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """Root endpoint — returns API information."""
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    """
    Health check endpoint.
    """
    from database import SessionLocal
    db = SessionLocal()
    try:
        total = db.query(models.Tender).count()
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
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.get("/admin/scraper-status")
def scraper_status():
    """
    Get status of all scraper sources.
    """
    from database import SessionLocal
    db = SessionLocal()
    try:
        rows = db.query(models.ScraperStatus).order_by(
            models.ScraperStatus.last_scraped_at.desc()
        ).all()
        
        return [
            {
                "site": s.site_name,
                "last_scraped": s.last_scraped_at.isoformat() if s.last_scraped_at else None,
                "result_count": s.last_result_count,
                "is_healthy": s.is_healthy,
                "last_error": s.last_error,
            }
            for s in rows
        ]
    finally:
        db.close()


@app.post("/admin/trigger-scrape")
async def trigger_scrape(background_tasks: BackgroundTasks):
    """
    Manually trigger a full scraper run.
    """
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
    """
    Get the current status of the scraper scheduler.
    """
    return get_scheduler_status()


# =============================================================================
# ERROR HANDLERS — FIXED: Return JSONResponse, not dict
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested resource was not found",
            "path": str(request.url),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler."""
    logger.error(f"[MAIN] Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info(f"[MAIN] Starting uvicorn server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )