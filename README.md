# TenderScout ZA – South African Tender Aggregation Platform

TenderScout ZA is a real‑time tender aggregation system that crawls, scrapes, and indexes tender opportunities from South African municipal and provincial portals, as well as national aggregator sites. It provides a clean, filterable web interface where users can search for tenders by industry, province, municipality, or keyword – with a credit‑based usage model.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture Overview](#architecture-overview)
- [How It Works](#how-it-works)
- [Setup & Installation](#setup--installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Screenshots (Conceptual)](#screenshots-conceptual)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Features

- **Automated Tender Discovery**  
  Crawls 50+ South African government portals (municipalities, districts, provincial governments) and national aggregators (`sa-tenders.co.za`, `etenders.gov.za`, `tenderalerts.co.za`, etc.).

- **Intelligent Province & Municipality Detection**  
  Uses city‑to‑province mapping and keyword analysis to correctly assign each tender to one of the 9 provinces and its local municipality – even when the source portal is a national aggregator.

- **Expired Tender Filtering**  
  Parses closing dates in various South African formats (e.g., `DD/MM/YYYY`, `DD Month YYYY`) and automatically excludes tenders with past closing dates from search results.

- **Incremental Scraping**  
  The system runs every 60 seconds, but only fetches listing pages to discover new links. Detail pages are scraped only for previously unseen tenders, dramatically reducing load.

- **Credit‑Based Search**  
  Each search result consumes 1 credit. New users receive 5 free credits; additional credits can be purchased (demo mode).

- **User Preferences**  
  Users can save preferred industries and provinces. The dashboard automatically shows relevant tenders based on these preferences.

- **Document Proxy**  
  A secure proxy endpoint allows PDF documents to be viewed inline without exposing the original URL or causing CORS issues.

- **Responsive Frontend**  
  Built with React, Tailwind CSS, and Lucide icons – works on desktop and mobile.

---

## Tech Stack

| Layer       | Technology                                                      |
|-------------|-----------------------------------------------------------------|
| Backend API | FastAPI (Python 3.12)                                           |
| Scraping    | `httpx`, `BeautifulSoup4`, `lxml`                               |
| Crawler     | Custom BFS crawler with `robots.txt` respect and stale‑year skip|
| Database    | SQLite (default) / PostgreSQL (optional)                        |
| ORM         | SQLAlchemy                                                      |
| Auth        | JWT (via `python-jose`), bcrypt hashing                         |
| Scheduler   | APScheduler (runs scraper every 60 seconds)                     |
| Frontend    | React 18, React Router, Axios                                   |
| Styling     | Tailwind CSS                                                    |
| PDF Viewer  | `react-pdf`                                                     |

---


---

## How It Works

### 1. Discovery (Crawler)
- The crawler starts from known seed URLs (e.g., `https://www.ncgov.co.za/tenders`).
- It performs a BFS up to a configurable depth, respecting `robots.txt`.
- For each found URL, it checks whether the URL has been seen before (stored in `crawl_results` table).
- Only **new URLs** are passed to the scraper.

### 2. Scraping (Scraper)
- For each new URL, the scraper fetches the page and extracts:
  - Title, issuing body, closing date, reference number, document links.
- Province is detected using a two‑step method:
  - First, look for known city names (e.g., "Pretoria" → Gauteng).
  - If none found, fall back to province keywords (e.g., "gauteng", "north west").
- Municipality and town are detected within the identified province.
- If a closing date is found and it is in the past, the tender is discarded.

### 3. Storage
- Tenders are stored in the `tenders` table with a unique `content_hash` (MD5 of title + source URL) to prevent duplicates.
- Crawled URLs are stored in `crawl_results` to avoid re‑crawling.

### 4. User Interface
- Users register / log in.
- After login, they set their industry and province preferences (onboarding).
- The dashboard shows tenders matching those preferences (or the last search).
- The search page allows advanced filtering (industries, provinces, municipalities, towns, keywords). Each result costs 1 credit.
- Users can top up credits (demo – no real payment).
- PDF documents are proxied through `/proxy/pdf` to avoid CORS and to allow inline viewing.

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- Node.js 18+ (for frontend)
- Git

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/tenderscout-za.git
   cd tenderscout-za/backend

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/Mac
   venv\Scripts\activate          # Windows

3. **Install dependencies**
   ```bash
  pip install -r requirements.txt

4. **Set up environment variables**
   ```env
   DATABASE_URL=sqlite:///./tenderscout.db
   SECRET_KEY=your-secret-key-here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=10080
   FREE_CREDITS_ON_SIGNUP=5
   CREDITS_PER_RESULT=1
   SCRAPE_INTERVAL_SECONDS=60

5. **Create database**
   ```bash
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"

6. **Run the backend**
   ```bash
   python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
