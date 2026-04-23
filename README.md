# TenderScout ZA – South African Tender Aggregation Platform

TenderScout ZA is a real‑time tender aggregation system that crawls, scrapes, and indexes tender opportunities from **60+ South African municipal and provincial portals**, as well as national aggregator sites. It provides a clean, filterable web interface where users can search for tenders by industry, province, municipality, or keyword – with a credit‑based usage model.

**Currently indexes 3,500+ active tenders across all 9 provinces.**

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture Overview](#architecture-overview)
- [How It Works](#how-it-works)
- [Current Coverage](#current-coverage)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Features

### 🔍 Tender Discovery & Aggregation
- **60+ Sources**: Crawls municipal websites, district municipalities, provincial governments, and national aggregators
- **Multi-format support**: Tenders, Bids, RFQs, RFPs, Quotations, Procurement notices
- **Key aggregators**: eTenders.gov.za, EasyTenders.co.za, OnlineTenders.co.za, Municipalities.co.za
- **Deduplication**: Content hashing prevents duplicate tenders across sources

### 🗺️ Interactive Map
- **Province-zoomed view**: Map auto-centers on user's registered province
- **Location pins**: Color-coded markers (Green=Town, Amber=Municipality, Gray=Province)
- **Driving routes**: OSRM-powered route lines from user location to tender locations
- **District markers**: Aggregated tender counts per district with popup details
- **CartoDB Voyager tiles**: Clear roads, town names, and professional styling

### 🏷️ Intelligent Classification
- **20 Industry Categories**: Automatic classification using keyword detection
- **Geographic Detection**: Province → Municipality → Town assignment
- **Expired Tender Filtering**: Parses multiple South African date formats

### 👤 User Experience
- **Location-based registration**: Select province and town during signup
- **Credit system**: 5 free credits on signup, 1 credit per search result
- **User preferences**: Save industries, provinces, and business location
- **Live polling**: Dashboard checks for new tenders every 60 seconds
- **PDF viewer**: Built-in document viewer with page navigation and zoom
- **Responsive design**: Works on desktop and mobile

### 🔧 Automated Pipeline
- **4-Phase scraper**: Crawler → City Portals → Aggregators → JS Sites
- **Scheduled runs**: APScheduler runs daily (configurable interval)
- **Scraper health monitoring**: Track status of all 60+ sources

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend API | FastAPI (Python 3.12) |
| Scraping | `httpx`, `BeautifulSoup4`, `lxml`, `Playwright` (JS sites) |
| Crawler | Custom BFS crawler with `robots.txt` respect |
| Database | SQLite (default) / PostgreSQL (optional) |
| ORM | SQLAlchemy |
| Auth | JWT (via `python-jose`), bcrypt hashing |
| Scheduler | APScheduler |
| Frontend | React 18, React Router, Axios |
| Styling | Tailwind CSS |
| Icons | Lucide React |
| Maps | Leaflet + React-Leaflet |
| PDF Viewer | `react-pdf` |
| Routing | OSRM (Open Source Routing Machine) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       TENDERSCOUT ZA ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                │
│  │  SCHEDULER   │──▶│   ENGINE     │──▶│  DATABASE    │                │
│  │ (APScheduler)│   │(Orchestrator)│   │  (SQLite)    │                │
│  └──────────────┘   └──────┬───────┘   └──────┬───────┘                │
│                            │                   │                        │
│         ┌──────────────────┼───────────────────┼──────────────────┐     │
│         │                  │                   │                  │     │
│         ▼                  ▼                   ▼                  ▼     │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐  │
│  │  CRAWLER   │   │ CITY PORTALS │   │ AGGREGATORS  │   │   JS     │  │
│  │ (BFS URLs) │   │  (60+ sites) │   │(sa_tenders,  │   │ SCRAPER  │  │
│  └────────────┘   └──────────────┘   │  bulletins)  │   │(Playwright)│  │
│                                      └──────────────┘   └──────────┘  │
│         │                  │                   │                  │     │
│         ▼                  ▼                   ▼                  ▼     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    FASTAPI BACKEND (REST API)                     │   │
│  │  /auth  /tenders  /search  /credits  /user  /admin  /proxy       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                     │                                    │
│                                     ▼                                    │
│                        ┌───────────────────────┐                        │
│                        │   REACT FRONTEND      │                        │
│                        │   (Vite + Tailwind)   │                        │
│                        └───────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## How It Works

### Phase 1: Discovery (Crawler)
- Starts from **60+ seed URLs** (municipalities, districts, aggregators)
- Performs BFS up to depth 2-3, respecting `robots.txt`
- Validates URLs (skips PDFs, admin pages, expired year URLs)
- Saves discovered URLs to `crawl_results` table

### Phase 2: City Portals (Municipal Scraping)
- Scrapes URLs discovered by crawler using site-specific handlers
- Supports multiple scrape types: `links`, `phoca`, `phokwane`, `ga_segonyana`, etc.
- Extracts: title, issuing body, closing date, document links

### Phase 3: Static Aggregators & Bulletins
- Scrapes HTML aggregators (`sa_tenders.py`, `tender_bulletins.py`)
- Handles pagination and retry logic

### Phase 4: JavaScript-Rendered Sites (Playwright)
- Launches headless Chromium for JS-heavy sites
- Scrapes `EasyTenders` (all 9 provinces), `eTenders.gov.za`, `OnlineTenders`
- Handles infinite scroll, modals, and dynamic content

### Storage & Deduplication
- Each tender gets a unique `content_hash` (MD5 of title + source URL)
- `upsert_tenders()` inserts only new tenders, skips duplicates
- Tenders with past closing dates are filtered out

### API & Frontend
- FastAPI serves REST endpoints with JWT authentication
- React frontend with interactive map, search filters, and PDF viewer
- PDF documents proxied through `/proxy/pdf`

---

## Current Coverage

| Province | Tenders | Sources |
|----------|---------|---------|
| KwaZulu-Natal | 1,088 | 8 |
| Gauteng | 866 | 5 |
| Northern Cape | 753 | 8 |
| Free State | 386 | 5 |
| Eastern Cape | 155 | 8 |
| Western Cape | 119 | 8 |
| Limpopo | 60 | 6 |
| Mpumalanga | 57 | 6 |
| North West | 55 | 6 |
| National | 4 | 3 |
| **TOTAL** | **3,543** | **60+** |

### Top Industry Categories

| Industry | Count |
|----------|-------|
| General | 2,863 |
| IT & Telecoms | 164 |
| Materials, Supply & Services | 82 |
| Building & Trades | 73 |
| Security, Access & Fire | 69 |
| Engineering Consultants | 55 |
| Plumbing & Water | 48 |
| Electrical & Automation | 30 |
| Mechanical, Plant & Equipment | 23 |
| Accounting, Banking & Legal | 18 |

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- Node.js 18+ (for frontend)
- Git
- Playwright (for JS scraping)

### Backend Setup

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/tenderscout-za.git
cd tenderscout-za/backend
```

**2. Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
playwright install chromium   # Required for JS scraping
```

**4. Set up environment variables**
```env
DATABASE_URL=sqlite:///./tenderscout.db
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
FREE_CREDITS_ON_SIGNUP=5
CREDITS_PER_RESULT=1
SCRAPE_INTERVAL_SECONDS=21600   # 6 hours
```

**5. Create database**
```bash
python scripts/create_db.py
```

**6. Run the backend**
```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**7. (Optional) Run initial scrape**
```bash
python -c "import asyncio; from scraper.engine import run_scraper; asyncio.run(run_scraper())"
```

### Frontend Setup

**1. Navigate to frontend directory**
```bash
cd ../frontend
```

**2. Install dependencies**
```bash
npm install
```

**3. Set up environment variables**
```env
VITE_API_URL=http://localhost:8000
```

**4. Run the frontend**
```bash
npm run dev
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:///./tenderscout.db` |
| `SECRET_KEY` | JWT signing secret | *Required* |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry in minutes | `10080` (7 days) |
| `FREE_CREDITS_ON_SIGNUP` | Credits given to new users | `5` |
| `CREDITS_PER_RESULT` | Credits consumed per search result | `1` |
| `SCRAPE_INTERVAL_SECONDS` | Interval between scraper runs | `21600` (6 hours) |
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | `http://localhost:5173,http://localhost:3000` |

---

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/` | API information | No |
| GET | `/health` | Basic health check | No |
| GET | `/health/detailed` | Comprehensive system health | No |
| POST | `/auth/register` | User registration (now accepts province/town) | No |
| POST | `/auth/login` | User login | No |
| GET | `/user/profile` | Get user profile | Yes |
| PUT | `/user/preferences` | Update preferences | Yes |
| GET | `/user/transactions` | Transaction history | Yes |
| GET | `/tenders/latest` | Latest tenders with filters | Yes |
| GET | `/tenders/{id}` | Single tender details | Yes |
| POST | `/search/tenders` | Search tenders (costs credits) | Yes |
| GET | `/search/history` | Search history | Yes |
| GET | `/credits/balance` | Credit balance | Yes |
| POST | `/credits/topup` | Purchase credits (demo) | Yes |
| GET | `/admin/scraper-status` | Scraper health status | No |
| POST | `/admin/trigger-scrape` | Manual scrape trigger | No |
| GET | `/proxy/pdf` | PDF document proxy | No |

---

## Project Structure

```
backend/
├── main.py                   # FastAPI application entry point
├── models.py                 # SQLAlchemy database models
├── schemas.py                # Pydantic schemas for API
├── database.py               # Database connection
├── auth_utils.py             # JWT authentication utilities
├── notifications.py          # Email/alert utilities
│
├── scraper/
│   ├── engine.py             # Main orchestrator (4-phase pipeline)
│   ├── crawler.py            # BFS crawler for URL discovery
│   ├── scheduler.py          # APScheduler for automated runs
│   ├── utils.py              # Shared utilities (detection, parsing)
│   │
│   └── sites/
│       ├── registry.py       # Single source of truth for all sources
│       ├── city_portals.py   # Municipal scrapers (60+ handlers)
│       ├── sa_tenders.py     # Aggregator scrapers
│       ├── tender_bulletins.py # Bulletin scrapers
│       ├── js_scraper.py     # Playwright JS scrapers
│       └── etenders.py       # eTenders.gov.za scraper
│
├── routers/
│   ├── auth.py               # Authentication endpoints
│   ├── tenders.py            # Tender endpoints
│   ├── search.py             # Search endpoints
│   ├── credits.py            # Credit management
│   ├── user.py               # User profile
│   └── proxy.py              # PDF proxy
│
└── scripts/
    ├── create_db.py          # Database initialization
    ├── show_provinces.py     # Province distribution stats
    ├── test_all_scrapers.py  # Full scraper test suite
    └── debug_selectors.py    # CSS selector debugging

frontend/src/
├── main.jsx                  # Application entry point
├── App.jsx                   # Root component with routing
├── index.css                 # Tailwind CSS
│
├── api/
│   ├── client.js             # Axios configuration
│   ├── auth.js               # Auth API calls
│   ├── tenders.js            # Tender API calls
│   └── credits.js            # Credit API calls
│
├── context/
│   └── AuthContext.jsx       # Global auth state
│
├── data/
│   └── saLications.js        # SA geographic data + routing
│
├── components/
│   ├── Layout.jsx            # Main layout (sidebar + header)
│   ├── TenderCard.jsx        # Tender display card
│   ├── TenderDrawer.jsx      # PDF viewer + detail drawer
│   ├── TenderMap.jsx         # Interactive map component
│   ├── LocationPicker.jsx    # Map-based location selector
│   └── ErrorBoundary.jsx     # Error handling wrapper
│
└── pages/
    ├── Login.jsx             # User login
    ├── Register.jsx          # User registration with location
    ├── Onboarding.jsx        # First-time preferences wizard
    ├── Dashboard.jsx         # Main dashboard with live polling
    ├── Search.jsx            # Advanced search + interactive map
    ├── Account.jsx           # User account settings
    └── TopUp.jsx             # Credit purchase
```

---

## Future Improvements

- [ ] PostgreSQL migration for production
- [ ] Redis caching for frequently accessed tenders
- [ ] Real payment integration (PayFast / Stripe)
- [ ] Email alerts for saved searches
- [ ] Machine learning for better industry classification
- [ ] Mobile app (React Native)
- [ ] API rate limiting
- [ ] Docker containerization
- [ ] CI/CD pipeline

---

## License

MIT License – See [LICENSE](LICENSE) file for details.

---

**Built for South African businesses seeking procurement opportunities.**
