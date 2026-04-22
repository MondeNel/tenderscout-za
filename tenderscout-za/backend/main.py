# MUST be first — fixes Windows ProactorEventLoop before uvicorn creates anything
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime
from typing import Optional

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

## Features
- **Search tenders** across all 9 provinces
- **Filter by industry** (20+ categories)
- **Geographic filtering** by municipality and town
- **Automated scraping** from 60+ government sources
- **Real-time updates** with scheduled scraping

## Authentication
Most endpoints require JWT authentication. Obtain a token via `/auth/login`.

## Credits
Search operations consume credits. Check your balance at `/credits/balance`.
"""

# =============================================================================
# APPLICATION LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Startup:
        - Create database tables if they don't exist
        - Start the scraper scheduler
        
    Shutdown:
        - Gracefully stop the scheduler
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
    openapi_tags=[
        {"name": "auth", "description": "Authentication operations"},
        {"name": "tenders", "description": "Tender search and retrieval"},
        {"name": "credits", "description": "Credit balance and transactions"},
        {"name": "user", "description": "User profile management"},
        {"name": "admin", "description": "Administrative operations"},
        {"name": "health", "description": "Health check endpoints"},
    ],
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

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(credits.router, prefix="/credits", tags=["credits"])
app.include_router(search.router, prefix="/search", tags=["tenders"])
app.include_router(tenders.router, prefix="/tenders", tags=["tenders"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(proxy_router, prefix="/proxy", tags=["proxy"])


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@app.get("/", tags=["health"])
def root():
    """Root endpoint — returns API information."""
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
def health():
    """
    Health check endpoint.
    
    Returns:
        - API status
        - Database connection status
        - Total and active tender counts
    """
    from database import SessionLocal
    db = SessionLocal()
    try:
        total = db.query(models.Tender).count()
        active = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        
        # Check if we can query the database
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


@app.get("/health/detailed", tags=["health"])
def detailed_health():
    """
    Detailed health check with scheduler and scraper status.
    
    Returns comprehensive system health information.
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        # Database stats
        total_tenders = db.query(models.Tender).count()
        active_tenders = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        
        # Scraper health
        scraper_statuses = db.query(models.ScraperStatus).all()
        healthy_scrapers = sum(1 for s in scraper_statuses if s.is_healthy)
        unhealthy_scrapers = len(scraper_statuses) - healthy_scrapers
        
        # Scheduler status
        scheduler_status = get_scheduler_status()
        
        # Recent activity
        last_scrape = db.query(models.ScraperStatus).order_by(
            models.ScraperStatus.last_scraped_at.desc()
        ).first()
        
        return {
            "status": "healthy" if unhealthy_scrapers == 0 else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "connected": True,
                "total_tenders": total_tenders,
                "active_tenders": active_tenders,
            },
            "scrapers": {
                "total": len(scraper_statuses),
                "healthy": healthy_scrapers,
                "unhealthy": unhealthy_scrapers,
            },
            "scheduler": scheduler_status,
            "last_scrape": {
                "site": last_scrape.site_name if last_scrape else None,
                "time": last_scrape.last_scraped_at.isoformat() if last_scrape and last_scrape.last_scraped_at else None,
            },
        }
    except Exception as e:
        logger.error(f"[MAIN] Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.get("/admin/scraper-status", tags=["admin"])
def scraper_status():
    """
    Get status of all scraper sources.
    
    Returns:
        List of scraper statuses with health information.
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


@app.post("/admin/trigger-scrape", tags=["admin"])
async def trigger_scrape(background_tasks: BackgroundTasks):
    """
    Manually trigger a full scraper run.
    
    The scrape runs in the background and does not block the response.
    
    Returns:
        Confirmation that the scrape was triggered.
    """
    from scraper.engine import run_scraper
    
    # Add to background tasks instead of create_task for better FastAPI integration
    background_tasks.add_task(run_scraper)
    
    logger.info("[MAIN] Manual scraper run triggered via admin endpoint")
    
    return {
        "status": "scrape triggered",
        "message": "Scraper is running in the background. Check /admin/scraper-status for results.",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/admin/scheduler-status", tags=["admin"])
def scheduler_status():
    """
    Get the current status of the scraper scheduler.
    
    Returns:
        Scheduler status including next run times.
    """
    return get_scheduler_status()


@app.get("/admin/stats", tags=["admin"])
def admin_stats():
    """
    Get comprehensive platform statistics.
    
    Returns:
        Tender counts by province, industry, and source.
    """
    from database import SessionLocal
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        # Total counts
        total_tenders = db.query(models.Tender).count()
        active_tenders = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        total_users = db.query(models.User).count()
        total_searches = db.query(models.SearchLog).count()
        
        # By province
        province_stats = db.query(
            models.Tender.province,
            func.count(models.Tender.id).label("count")
        ).group_by(models.Tender.province).all()
        
        # By industry
        industry_stats = db.query(
            models.Tender.industry_category,
            func.count(models.Tender.id).label("count")
        ).group_by(models.Tender.industry_category).all()
        
        # By source
        source_stats = db.query(
            models.Tender.source_site,
            func.count(models.Tender.id).label("count")
        ).group_by(models.Tender.source_site).order_by(func.count(models.Tender.id).desc()).limit(10).all()
        
        return {
            "summary": {
                "total_tenders": total_tenders,
                "active_tenders": active_tenders,
                "total_users": total_users,
                "total_searches": total_searches,
            },
            "by_province": {p: c for p, c in province_stats if p},
            "by_industry": {i: c for i, c in industry_stats if i},
            "top_sources": {s: c for s, c in source_stats if s},
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler."""
    return {
        "error": "Not Found",
        "message": "The requested resource was not found",
        "path": str(request.url),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler."""
    logger.error(f"[MAIN] Internal server error: {exc}")
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "timestamp": datetime.utcnow().isoformat(),
    }


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