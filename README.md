# TenderScout ZA – South African Tender Aggregation Platform

A friend of mine was spending hours each week manually checking government websites to track procurement opportunities — opening the same 10+ portals every morning just to stay on top of what was available. I built TenderScout ZA to fix that.

TenderScout is a real-time tender aggregation system that crawls, scrapes, and indexes tender opportunities from South African municipal and provincial portals, as well as national aggregator sites. It provides a clean, filterable web interface where users can search for tenders by industry, province, municipality, or keyword — with a credit-based usage model.

I also used this project deliberately to learn how to build web crawlers and scrapers from scratch. The crawler now covers **60+ sources** across all 9 provinces and indexes **3,500+ active tenders**. Building it taught me BFS crawl strategies, `robots.txt` compliance, deduplication via content hashing, geographic entity detection, and handling sites that require JavaScript rendering via Playwright — skills I would not have picked up building standard CRUD applications.

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

## 🏗️ Architecture Overview

The project is split into two top-level folders — `backend/` (FastAPI) and `frontend/` (React + Vite).

| Layer | Folder / File | Responsibility |
|---|---|---|
| **API** | `backend/main.py`, `backend/routers/` | FastAPI entry point and all route handlers |
| **Scraping engine** | `backend/scraper/` | Orchestrator, BFS crawler, scheduler, site-specific scrapers |
| **Data models** | `backend/models.py`, `schemas.py`, `database.py` | SQLAlchemy ORM, Pydantic schemas, DB connection |
| **Utilities & scripts** | `backend/auth_utils.py`, `scripts/` | Auth, alerts, DB init, scraper tests, debugging tools |
| **Frontend** | `frontend/src/` | React pages, components, API clients, context, static data |

### Backend

```
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
│   ├── engine.py           # Orchestrates the 4-phase pipeline
│   ├── crawler.py          # BFS crawler — discovers URLs, respects robots.txt
│   ├── scheduler.py        # APScheduler — runs the full pipeline daily
│   ├── utils.py            # Shared helpers: geo detection, date parsing, deduplication
│   │
│   └── sites/
│       ├── registry.py         # Single source of truth for all 60+ sources
│       ├── city_portals.py     # Municipal portal scrapers
│       ├── sa_tenders.py       # National aggregator scrapers
│       ├── tender_bulletins.py # Bulletin-style scrapers
│       ├── js_scraper.py       # Playwright scrapers for JS-rendered pages
│       └── etenders.py         # eTenders.gov.za scraper
│
├── routers/
│   ├── auth.py             # Register, login, JWT token management
│   ├── tenders.py          # Tender listing and detail endpoints
│   ├── search.py           # Filtered search with credit deduction
│   ├── credits.py          # Credit balance and purchase
│   ├── user.py             # User profile and preferences
│   └── proxy.py            # PDF document proxy
│
└── scripts/
    ├── create_db.py            # Database initialisation
    ├── show_provinces.py       # Province distribution stats
    ├── test_all_scrapers.py    # Full scraper test suite
    ├── debug_selectors.py      # CSS selector debugging
    └── test_db_schema.py       # Schema verification
```

### Frontend

```
frontend/
├── public/
└── src/
    ├── api/
    │   ├── auth.js             # Auth API calls
    │   ├── client.js           # Axios base client
    │   ├── credits.js          # Credits API calls
    │   ├── industries.js       # Industry lookup
    │   └── tenders.js          # Tender API calls
    │
    ├── components/
    │   ├── ErrorBoundary.jsx
    │   ├── IndustryCheckboxGroup.jsx
    │   ├── Layout.jsx
    │   ├── LoadingSpinner.jsx
    │   ├── LocationPicker.jsx
    │   ├── TenderCard.jsx
    │   ├── TenderDrawer.jsx
    │   └── TenderMap.jsx
    │
    ├── context/
    │   └── AuthContext.jsx     # Global auth state
    │
    ├── data/
    │   └── saLocations.js      # Static SA province/municipality data
    │
    ├── pages/
    │   ├── Account.jsx
    │   ├── Dashboard.jsx
    │   ├── Login.jsx
    │   ├── Onboarding.jsx
    │   ├── Profile.jsx
    │   ├── Register.jsx
    │   ├── Search.jsx
    │   └── TopUp.jsx
    │
    ├── App.css
    ├── App.jsx
    ├── index.css
    └── main.jsx
│
├── index.html
├── package.json
├── postcss.config.js
├── tailwind.config.js
└── vite.config.js
```
