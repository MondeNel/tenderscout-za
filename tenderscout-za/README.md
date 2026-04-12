# TenderScout ZA

> Real-time government and municipal tender aggregation platform for South Africa — powered by a crawler + scraper engine.

---

## What is this?

TenderScout ZA is a SaaS web application that continuously discovers and scrapes South African government and municipal websites for tender opportunities, surfacing them to procurement companies in real time.

Companies register, select their service industries and provinces, and receive a live feed of relevant tenders — charged per result on a credit-based model.

---

## How the Crawler + Scraper Engine Works

The system runs on a two-phase intelligence engine that fires every 60 seconds.

### Phase 1 — Crawler (Discovery)
The crawler visits the root URL of each configured site and walks the site's internal link structure up to 3 levels deep. It builds a verified index of URLs that:
- Responded with HTTP 200 (alive)
- Contain tender-related keywords in the URL or anchor text
- Belong to the same domain (no external link following)
- Have not been crawled recently (respects a crawl cache)

The crawler is polite — it waits 1 second between requests, caps at 50 pages per site per cycle, and respects robots.txt disallowed paths.

### Phase 2 — Scraper (Extraction)
The scraper receives the verified URL index from the crawler and visits each page to extract structured tender data:
- Title
- Description / body text
- Reference number
- Issuing body
- Closing date / deadline
- Posted date
- Source URL (the live page, not a download link)
- Province + town (auto-detected from content)
- Industry category (auto-detected from keywords)

Results are deduplicated by content hash (MD5 of title + URL) before being stored.

### Why This Solves the 404 Problem
The old approach hardcoded URLs and hoped the links were still alive. The crawler verifies every URL before the scraper touches it — only live pages enter the pipeline. No more dead links sent to users.

```
SCHEDULER (every 60s)
       |
       v
  CRAWLER (Phase 1)
  - Visits root URL
  - Follows internal links (depth <= 3)
  - Filters by tender keywords
  - Verifies HTTP 200
  - Returns: live URL index
       |
       v
  SCRAPER (Phase 2)
  - Receives URL index
  - Extracts structured data per page
  - Detects industry + province
  - Deduplicates by content hash
  - Stores new tenders to DB
       |
       v
  EMAIL NOTIFICATION
  - Fires if new_count > 0
  - Sends digest to admin email
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite, Tailwind CSS, React Router v7, Axios |
| Backend | Python 3.12, FastAPI, SQLAlchemy ORM |
| Database | SQLite (file-based, upgradeable to PostgreSQL) |
| Crawler | httpx async + URL frontier queue + depth control |
| Scraper | BeautifulSoup4 + lxml (async, per-site extractors) |
| Scheduling | APScheduler (AsyncIO, 60s interval) |
| Auth | JWT tokens via python-jose + passlib bcrypt |
| Email | Gmail SMTP (smtplib) for tender notifications |

---

## Features Completed

### Backend
- FastAPI app with full CORS, lifespan management, modular routers
- SQLite database with SQLAlchemy models: User, Tender, SearchLog, Transaction, ScraperStatus
- JWT authentication: register, login, protected routes
- Credit system: 50 free credits on signup, 1 credit per search result
- Top-up packages: R100 (10 credits), R250 (25 credits), R500 (50 credits) — mocked
- Background scheduler: fires every 60 seconds, non-blocking async
- Deduplication: content hash prevents duplicate tenders
- Per-cycle terminal report table: source, scraped count, new count, HTTP status
- Email notifications via Gmail SMTP when new tenders are found
- Industry keyword detection: 14 categories auto-tagged
- Province keyword detection: all 9 SA provinces auto-detected
- Stale tender filtering: URLs containing old years (2018-2024) are skipped
- Source URL strategy: always stores listing page URL, never ephemeral download links

### Scraper Sources (active)
| Source | Type | Status |
|---|---|---|
| City of Ekurhuleni (ekurhuleni.gov.za) | Municipal | Working |
| Buffalo City Metro (buffalocity.gov.za) | Municipal | Working |
| Nelson Mandela Bay (nelsonmandelabay.gov.za) | Municipal | Working |
| Siyathemba Municipality (siyathemba.gov.za) | Municipal | Working |
| Northern Cape DEDAT (northern-cape.gov.za) | Provincial | Working |
| sa-tenders.co.za | Aggregator | Needs selector tuning |
| tenderbulletins.co.za | Aggregator | 403 Forbidden |
| Cape Town, Joburg, Tshwane, Durban, Mangaung | Municipal | 404 — URLs changed |

### Crawler (in progress)
- Async BFS crawler with configurable depth limit (default: 3)
- URL frontier queue with visited set (no loops)
- Keyword filtering: only follows links containing tender-related terms
- Domain boundary enforcement: same domain only
- Politeness: 1s delay between requests, 50 page cap per site per cycle
- robots.txt awareness
- Crawl result feeds directly into scraper pipeline
- CrawlResult model: stores discovered URLs with metadata per site

### Frontend
- React SPA with React Router v7
- Auth flow: Register → Onboarding → Dashboard
- Onboarding: 2-step wizard (industry + province selection)
- Dashboard: live tender feed, reads filters from last search, 60s polling, new tender toast
- Search page: keyword + industry + province filters, paginated, credit deduction, saves filters to shared context
- Shared search context: filters set on Search page automatically update Dashboard
- Account page: update preferences, transaction history
- Top Up page: select credit package, mock payment
- Mobile responsive layout with hamburger drawer navigation
- Credit balance shown live in sidebar
- URL validation: invalid/dead links show 'Link unavailable' instead of broken redirect
- 'View on site' links go to listing pages, not individual documents

---

## Project Structure

```
tenderscout-za/
  backend/
    main.py                  FastAPI app + lifespan + CORS
    database.py              SQLAlchemy engine + session
    models.py                DB models (User, Tender, SearchLog, Transaction, ScraperStatus, CrawlResult)
    schemas.py               Pydantic schemas
    auth.py                  JWT utils
    notifications.py         Gmail SMTP email alerts
    routers/
      auth.py                /auth/register, /auth/login
      user.py                /user/profile, /user/preferences
      tenders.py             /tenders/latest, /tenders/:id
      search.py              /search/tenders, /search/history
      credits.py             /credits/balance, /credits/topup
    scraper/
      engine.py              Orchestrator: runs crawler then scraper, builds report table
      scheduler.py           APScheduler 60s job
      crawler.py             Async BFS crawler — discovers + verifies live URLs
      utils.py               Industry/province detection, hashing, headers, expiry filter
      sites/
        sa_tenders.py        sa-tenders.co.za extractor
        tender_bulletins.py  tenderbulletins.co.za extractor
        city_portals.py      Municipal portals (generic links + Phoca Download extractors)
  frontend/
    src/
      api/                   axios API clients (auth, tenders, credits)
      components/            Layout (sidebar + mobile hamburger nav)
      context/               AuthContext (JWT + user state + shared search filters)
      pages/
        Dashboard.jsx        Live feed, reads lastSearch context, filter pills, polling
        Search.jsx           Keyword + industry + province search, saves filters to context
        Account.jsx          Preferences, transaction history
        TopUp.jsx            Credit packages, mock payment
        Login.jsx            JWT login
        Register.jsx         Register + redirect to onboarding
        Onboarding.jsx       2-step industry + province wizard
```

---

## Running Locally

### Backend
```bash
cd backend
source venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# App: http://localhost:5173
```

### Email Setup (optional)
1. Enable 2FA on your Google account
2. myaccount.google.com > Security > App Passwords > create one for TenderScout
3. Add to backend/.env:
```
GMAIL_USER=mondenel1996@gmail.com
GMAIL_PASSWORD=your_app_password_here
```

---

## Environment Variables (backend/.env)

```
SECRET_KEY=tenderscout-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
DATABASE_URL=sqlite:///./tenderscout.db
SCRAPE_INTERVAL_SECONDS=60
FREE_CREDITS_ON_SIGNUP=50
CREDITS_PER_RESULT=1
GMAIL_USER=mondenel1996@gmail.com
GMAIL_PASSWORD=
```

---

## What Needs To Be Done Next

### Crawler (immediate)
- Build scraper/crawler.py — async BFS with depth control and keyword filtering
- Add CrawlResult model to DB for storing discovered URL index
- Wire crawler output into engine.py before scraper phase
- Test against Siyathemba and Ekurhuleni as first targets
- Add per-site crawl config (max_depth, max_pages, seed_urls)

### Scraper improvements
- Fix broken municipal URLs (Cape Town, Joburg, Tshwane, Durban, Mangaung)
- Tune CSS selectors for sa-tenders.co.za
- Handle tenderbulletins.co.za 403 (rotate headers/user agents)
- Add etenders.gov.za via official government API
- Extract closing dates more reliably (date parsing)
- Extract reference numbers from tender titles

### Platform
- Add real payment gateway (Yoco or PayFast — SA-native)
- Upgrade database to PostgreSQL for production
- Deploy backend to Railway or Render
- Deploy frontend to Vercel or Netlify
- Add per-user email alerts (not just admin notifications)
- Add tender detail page with full description
- Add saved/bookmarked tenders feature
- Add user dashboard analytics (searches, credits spent, tenders viewed)
- Rate limiting on API endpoints
- Proxy rotation for scraper in production
- Admin dashboard to monitor scraper health per site
