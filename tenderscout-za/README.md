# TenderScout ZA

> Real-time government and municipal tender aggregation platform for South Africa.

## What is this?

TenderScout ZA is a SaaS web application that continuously scrapes South African government and municipal websites for tender opportunities, and surfaces them to procurement companies in real time. Companies register, select their service industries and provinces, and receive a live feed of relevant tenders — charged per result on a credit-based model.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite, Tailwind CSS, React Router, Axios |
| Backend | Python 3.12, FastAPI, SQLAlchemy ORM |
| Database | SQLite (file-based, upgradeable to PostgreSQL) |
| Scraping | httpx + BeautifulSoup4 + lxml (async) |
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
- Background scraper scheduler: fires every 60 seconds, non-blocking async
- Deduplication: content hash (MD5 of title + URL) prevents duplicate tenders
- Per-cycle terminal report table showing each source, scraped count, new count, status
- Email notifications via Gmail SMTP when new tenders are found
- Industry keyword detection: 14 categories auto-tagged on scraped content
- Province keyword detection: all 9 SA provinces auto-detected

### Scraper Sources (active)
| Source | Status |
|---|---|
| City of Ekurhuleni (ekurhuleni.gov.za) | Working |
| Buffalo City Metro (buffalocity.gov.za) | Working |
| Nelson Mandela Bay (nelsonmandelabay.gov.za) | Working |
| Siyathemba Municipality (siyathemba.gov.za) | Working |
| Northern Cape DEDAT (northern-cape.gov.za) | Working |
| sa-tenders.co.za | Needs selector tuning |
| tenderbulletins.co.za | 403 Forbidden |
| Cape Town, Joburg, Tshwane, Durban, Mangaung | 404 — URLs changed |

### Frontend
- React SPA with React Router v7
- Auth flow: Register → Onboarding → Dashboard
- Onboarding: 2-step wizard (industry selection + province selection)
- Dashboard: live tender feed, filter by industry/province, 60s polling, new tender toast
- Search page: keyword + industry + province filters, paginated results, credit deduction
- Account page: update preferences, transaction history
- Top Up page: select credit package, mock payment
- Mobile responsive layout with hamburger drawer
- Credit balance shown in sidebar (live)

---

## Project Structure

```
tenderscout-za/
  backend/
    main.py               FastAPI app + lifespan + CORS
    database.py           SQLAlchemy engine + session
    models.py             DB models
    schemas.py            Pydantic schemas
    auth.py               JWT utils
    notifications.py      Gmail SMTP email alerts
    routers/
      auth.py             /auth/register, /auth/login
      user.py             /user/profile, /user/preferences
      tenders.py          /tenders/latest, /tenders/:id
      search.py           /search/tenders, /search/history
      credits.py          /credits/balance, /credits/topup
    scraper/
      engine.py           Orchestrator + DB upsert + report table
      scheduler.py        APScheduler 60s job
      utils.py            Industry/province detection, hashing, headers
      sites/
        sa_tenders.py     sa-tenders.co.za scraper
        tender_bulletins.py tenderbulletins.co.za scraper
        city_portals.py   All municipal portals (generic + phoca scrapers)
  frontend/
    src/
      api/                axios API clients
      components/         Layout (sidebar + mobile nav)
      context/            AuthContext (JWT + user state)
      pages/              Dashboard, Search, Account, TopUp, Login, Register, Onboarding
```

---

## Running Locally

### Backend
```bash
cd backend
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Email Setup (optional)
1. Enable 2FA on your Google account
2. Go to myaccount.google.com > Security > App Passwords
3. Create a password for TenderScout
4. Add to backend/.env:
```
GMAIL_USER=mondenel1996@gmail.com
GMAIL_PASSWORD=your_app_password_here
```

---

## What Needs To Be Done Next

- Fix broken scraper URLs (Cape Town, Joburg, Tshwane, Durban, Mangaung)
- Add more scraper sources (etenders.gov.za API, more municipalities)
- Tune CSS selectors for sa-tenders.co.za
- Add real payment gateway (Yoco or PayFast)
- Upgrade database to PostgreSQL for production
- Deploy backend to Railway/Render
- Deploy frontend to Vercel/Netlify
- Add user email alerts (per-user preferences, not just admin)
- Add tender detail page with full description
- Add saved/bookmarked tenders feature
- Rate limiting and scraper proxy rotation for production
