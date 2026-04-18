from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
import models
from database import engine
from routers import auth, credits, search, tenders, user
from routers.proxy import router as proxy_router
from scraper.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    logger.info("[MAIN] Database tables ensured")
    start_scheduler()
    logger.info("[MAIN] TenderScout ZA started")
    yield
    stop_scheduler()
    logger.info("[MAIN] TenderScout ZA stopped")


app = FastAPI(
    title="TenderScout ZA",
    description="South African government tender search platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(credits.router)
app.include_router(search.router)
app.include_router(tenders.router)
app.include_router(user.router)
app.include_router(proxy_router)


@app.get("/health")
def health():
    from database import SessionLocal
    db = SessionLocal()
    try:
        total  = db.query(models.Tender).count()
        active = db.query(models.Tender).filter(models.Tender.is_active == True).count()
        return {"status": "ok", "total_tenders": total, "active_tenders": active}
    finally:
        db.close()


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
async def trigger_scrape():
    """Manually kick off a scrape cycle without waiting for the scheduler."""
    from scraper.engine import run_scraper
    import asyncio
    asyncio.create_task(run_scraper())
    return {"status": "scrape triggered"}