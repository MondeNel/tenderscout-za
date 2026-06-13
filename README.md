# TenderScout ZA — South African Government Tender Aggregation Platform

## Why I built this

A friend of mine was spending hours each week manually checking government websites to track procurement opportunities — opening the same 10+ portals every morning just to stay on top of what was available.

I thought: *why does finding a public tender in South Africa require opening 20 browser tabs every single day?*

I started exploring the problem as a **FastAPI + SQLite backend**, because that stack is perfect for a lightweight scraping pipeline before committing to heavier infrastructure. While building it, I realised the scope was bigger than one city or province — there are **60+ active sources** across all 9 provinces, and none of them talk to each other.

**This repository is the full-stack platform I built to solve that.** A BFS crawler scrapes, deduplicates, and indexes tenders from municipal portals, provincial governments, and national aggregators — and surfaces everything in one searchable, filterable dashboard. The actual scraping engine, scheduling pipeline, and credit-based usage model are all live. This is not a prototype.

---

## Overview

TenderScout ZA is a real-time tender aggregation platform built for South Africa. It provides a single interface where procurement professionals, contractors, and SMEs can search 3,500+ active government tenders — filtered by province, municipality, industry, or keyword — without touching a single government portal directly.

**What makes it real:** The scraping pipeline, geographic detection, deduplication, JWT auth, and credit system are fully implemented. SQLite is used for rapid development before an eventual PostgreSQL migration.

Built with **FastAPI**, **React 18**, **Tailwind CSS**, **Playwright**, and **Leaflet**, the platform features automated daily scraping, PDF document proxying, interactive map views, and location-aware onboarding.

---

## Tech Stack

| Technology | Purpose |
|------------|---------|
| FastAPI (Python 3.12) | Backend API |
| SQLAlchemy + SQLite | ORM and database |
| httpx + BeautifulSoup4 | Lightweight HTTP scraping |
| Playwright | JS-rendered site scraping |
| APScheduler | Daily scraping pipeline |
| JWT (python-jose) | Authentication |
| React 18 + Vite | Frontend framework |
| Tailwind CSS | Styling |
| Leaflet | Interactive tender map |
| react-pdf | Inline PDF document viewer |

---

## Features

### 🔐 Authentication

- **Register**: Email, password, and region-based onboarding
- **Login**: JWT token issued on success, persisted in context
- **Onboarding**: Province, municipality, and industry preference selection on first login
- Location-aware dashboard on signup — tenders filtered to your region by default
- Protected routes with redirect for unauthenticated users

### 🔍 Search & Discovery

- Full-text search across 3,500+ indexed tenders
- Filter by **province**, **municipality**, **town**, **industry category**, or **keyword**
- 20 auto-classified industry categories (IT & Telecoms, Civil, Security, Building & Trades, etc.)
- Expired tender filtering — closing dates parsed in multiple SA date formats
- **Credit-based search**: each result set consumes 1 credit
- New users receive 5 free credits on registration

### 🗺️ Interactive Map

- Leaflet map with district-level tender density visualisation
- Tenders plotted by geographic entity detection (province → municipality → town)
- OSRM route overlays for field-based users

#### Dashboard
- Tender feed personalised to saved province, municipality, and industry preferences
- Stats overview: total indexed tenders, active sources, credits remaining
- Quick filters for saved preferences
- "Top Up Credits" flow for continued access

#### Tender Detail
- Full tender metadata: title, source, closing date, industry, location
- **Inline PDF viewer** — documents proxied securely to avoid CORS issues
- Direct link to source portal
- Closing date countdown

#### Account & Profile
- Saved industry and location preferences
- Credit balance and purchase history
- Profile management

---

## 🕷️ Scraping Engine

#### Coverage
- **60+ sources** across all 9 provinces
- Municipal portals, district municipalities, provincial governments
- National aggregators: `eTenders.gov.za`, `EasyTenders.co.za`, `OnlineTenders.co.za`, `Municipalities.co.za`

#### How it works
- **BFS crawler** discovers tender URLs from seed sources, respects `robots.txt`
- **Deduplication** via `content_hash` (MD5 of title + URL) — only new tenders inserted
- **Playwright** handles JS-rendered portals that httpx can't reach
- **Geographic entity detection** maps each tender to province → municipality → town using keyword analysis, even when scraped from a national aggregator
- **APScheduler** runs the full pipeline daily at a configurable interval

---

## 📱 Responsive Design

- **Mobile-first** approach throughout
- Dashboard and search views adapt to all screen sizes
- Tender cards collapse gracefully on narrow viewports
- PDF viewer works on desktop and mobile

---

## 📦 Project Structure

```
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── models.py                # SQLAlchemy models
│   ├── schemas.py               # Pydantic schemas
│   ├── database.py              # DB connection
│   ├── auth_utils.py            # JWT utilities
│   ├── notifications.py         # Alert utilities
│   │
│   ├── scraper/
│   │   ├── engine.py            # 4-phase pipeline orchestrator
│   │   ├── crawler.py           # BFS crawler, robots.txt compliance
│   │   ├── scheduler.py         # APScheduler daily runs
│   │   ├── utils.py             # Geo detection, date parsing, deduplication
│   │   └── sites/
│   │       ├── registry.py      # All 60+ source definitions
│   │       ├── city_portals.py  # Municipal scrapers
│   │       ├── sa_tenders.py    # National aggregator scrapers
│   │       ├── js_scraper.py    # Playwright scrapers
│   │       └── etenders.py      # eTenders.gov.za scraper
│   │
│   ├── routers/
│   │   ├── auth.py              # Register, login, JWT
│   │   ├── tenders.py           # Tender listing and detail
│   │   ├── search.py            # Filtered search + credit deduction
│   │   ├── credits.py           # Credit balance and purchase
│   │   ├── user.py              # Profile and preferences
│   │   └── proxy.py             # PDF document proxy
│   │
│   └── scripts/
│       ├── create_db.py         # DB initialisation
│       ├── show_provinces.py    # Province distribution stats
│       ├── test_all_scrapers.py # Full scraper test suite
│       └── debug_selectors.py  # CSS selector debugging
│
└── frontend/
    └── src/
        ├── api/                 # Axios API clients
        ├── components/          # Shared UI components
        ├── context/             # Auth context
        ├── data/                # Static SA location data
        └── pages/               # Route-level page components
            ├── Dashboard.jsx
            ├── Search.jsx
            ├── Account.jsx
            ├── Profile.jsx
            ├── Onboarding.jsx
            ├── Login.jsx
            ├── Register.jsx
            └── TopUp.jsx
```

---

## 🚀 Getting Started

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python scripts/create_db.py
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## ⚠️ Disclaimer

TenderScout ZA is an independent portfolio and educational project created to explore automated procurement discovery, web scraping pipelines, and civic data aggregation.

This project is not affiliated with, endorsed by, or associated with the South African Government, National Treasury, eTenders, any municipal or provincial authority, or any tender aggregator listed as a data source.

All scraping is performed on publicly accessible data. No authentication is bypassed. The platform does not guarantee the accuracy, completeness, or timeliness of indexed tenders. Users should verify all opportunities directly with the originating authority before acting on them.

---

# 🎥 Application Demonstration

## 🔍 Platform Walkthrough

Experience the complete TenderScout ZA journey:

* Registration & location-aware onboarding
* Tender search with province, municipality and industry filters
* Interactive map with district-level tender density
* Inline PDF document viewer
* Credit-based search model
* Account preferences and profile management

### ▶️ Platform Demo


https://github.com/user-attachments/assets/24b2b1f6-ab31-442d-ac52-2c68b1e4487d

