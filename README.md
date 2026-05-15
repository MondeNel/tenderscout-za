# TenderScout ZA – South African Tender Aggregation Platform

TenderScout ZA is a real‑time tender aggregation system that crawls, scrapes, and indexes tender opportunities from South African municipal and provincial portals, as well as national aggregator sites. It provides a clean, filterable web interface where users can search for tenders by industry, province, municipality, or keyword – with a credit‑based usage model.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture Overview](#architecture-overview)
- [How It Works](#how-it-works)
- [Current Coverage](#current-coverage)
- [Setup & Installation](#setup--installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Features

- **Nationwide Tender Coverage**  
  Aggregates tenders, bids, RFQs, and quotations from **60+ sources** across all 9 South African provinces. Currently indexes **3,500+ active tenders**.

- **Multi-Source Aggregation**  
  Scrapes municipal websites, district municipalities, provincial governments, and national aggregators including:
  - `eTenders.gov.za` (Official government portal)
  - `EasyTenders.co.za` (All 9 provinces)
  - `OnlineTenders.co.za`
  - `Municipalities.co.za`

- **Intelligent Geographic Detection**  
  Uses province-to-municipality-to-town mapping and keyword analysis to correctly assign each tender to its province and local municipality – even when the source is a national aggregator.

- **Industry Classification**  
  Automatically categorizes tenders into **20 industry categories** (IT & Telecoms, Building & Trades, Civil, Security, etc.) using keyword detection.

- **Expired Tender Filtering**  
  Parses closing dates in various South African formats and automatically excludes expired tenders from active search results.

- **Incremental Scraping with Deduplication**  
  Uses `content_hash` (MD5 of title + URL) to prevent duplicate tenders. Only new tenders are inserted.

- **Credit‑Based Search**  
  Each search result consumes 1 credit. New users receive 5 free credits; additional credits can be purchased (demo mode).

- **User Preferences & Alerts**  
  Users can save preferred industries, provinces, municipalities, and towns. The dashboard shows relevant tenders based on these preferences.

- **Automated Scheduling**  
  APScheduler runs the full scraping pipeline daily (configurable interval/cron) to keep tenders fresh.

- **Document Proxy**  
  Secure proxy endpoint allows PDF documents to be viewed inline without exposing the original URL or causing CORS issues.

- **Responsive Frontend**  
  Built with React, Tailwind CSS, and Lucide icons – works on desktop and mobile.

---

## Tech Stack

| Layer          | Technology                                                      |
|----------------|-----------------------------------------------------------------|
| Backend API    | FastAPI (Python 3.12)                                           |
| Scraping       | `httpx`, `BeautifulSoup4`, `lxml`, `Playwright` (for JS sites)  |
| Crawler        | Custom BFS crawler with `robots.txt` respect                    |
| Database       | SQLite (default) / PostgreSQL (optional)                        |
| ORM            | SQLAlchemy                                                      |
| Auth           | JWT (via `python-jose`), bcrypt hashing                         |
| Scheduler      | APScheduler (runs scraper daily / configurable interval)        |
| Frontend       | React 18, React Router, Axios                                   |
| Styling        | Tailwind CSS                                                    |
| PDF Viewer     | `react-pdf`                                                     |

---

## Architecture Overview
backend/
├── main.py                 # FastAPI application entry point
├── models.py               # SQLAlchemy database models
├── schemas.py              # Pydantic schemas for API
├── database.py             # Database connection
├── auth_utils.py           # JWT authentication utilities
├── notifications.py        # Email/alert utilities
├── requirements.txt        # Python dependencies
│
├── scraper/
│   ├── engine.py           # Main orchestrator (4-phase pipeline)
│   ├── crawler.py          # BFS crawler for URL discovery
│   ├── scheduler.py        # APScheduler for automated runs
│   ├── utils.py            # Shared utilities (detection, parsing)
│   │
│   └── sites/
│       ├── registry.py     # Single source of truth for all sources
│       ├── city_portals.py # Municipal scrapers (60+ handlers)
│       ├── sa_tenders.py   # Aggregator scrapers
│       ├── tender_bulletins.py # Bulletin scrapers
│       ├── js_scraper.py   # Playwright JS scrapers
│       └── etenders.py     # eTenders.gov.za scraper
│
├── routers/
│   ├── auth.py             # Authentication endpoints
│   ├── tenders.py          # Tender endpoints
│   ├── search.py           # Search endpoints
│   ├── credits.py          # Credit management
│   ├── user.py             # User profile
│   └── proxy.py            # PDF proxy
│
└── scripts/
    ├── create_db.py        # Database initialization
    ├── show_provinces.py   # Province distribution stats
    ├── test_all_scrapers.py # Full scraper test suite
    ├── debug_selectors.py  # CSS selector debugging
    └── test_db_schema.py   # Schema verification

    