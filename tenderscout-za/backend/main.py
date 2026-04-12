import warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import engine, Base
from scraper.scheduler import start_scheduler, stop_scheduler
from scraper.engine import run_scraper
from routers import auth, user, tenders, search, credits, proxy
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logging.info("[DB] Tables created")
    start_scheduler()  # scraper runs after first 60s interval, not blocking startup
    yield
    stop_scheduler()


app = FastAPI(
    title="TenderScout ZA API",
    description="Real-time tender aggregation platform for South Africa",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(tenders.router)
app.include_router(search.router)
app.include_router(credits.router)
app.include_router(proxy.router)


@app.get("/")
def root():
    return {"message": "TenderScout ZA API is running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
