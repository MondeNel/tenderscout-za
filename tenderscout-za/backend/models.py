"""
models.py — SQLAlchemy ORM Models for TenderScout ZA
======================================================
Defines every database table used by the application.
All models inherit from `Base` (imported from database.py)
so that `create_all` can generate the full schema.

Table summary:
- users             : registered company accounts
- tenders           : scraped tender opportunities
- search_logs       : audit trail of user searches
- transactions      : credit ledger (top‑ups, search debits)
- scraper_status    : per‑source health tracking
- crawl_results     : URLs discovered by the BFS crawler
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text,
    Boolean, JSON, Index, ForeignKey, Numeric
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


# ------------------------------------------------------------------
# USER
# ------------------------------------------------------------------
class User(Base):
    """
    Registered company account.

    Industry / province / town / municipality preferences are stored as
    JSON lists so the user can select multiple values. The convenience
    properties `industry_prefs`, `province_prefs`, etc. return an empty
    list when the column is NULL, avoiding None checks in application code.

    New company profile fields (v2):
    - company_name         : optional display name for the company
    - registration_number  : company registration number (e.g., 2024/123456/07)
    - bee_level            : B‑BBEE level ("1"–"4" or "Non‑compliant")
    - company_size         : "Micro", "Small", "Medium", or "Large"
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    full_name     = Column(String(255), nullable=False)

    # --- Company profile (v2) ---
    company_name         = Column(String(255), nullable=True)
    registration_number  = Column(String(100), nullable=True)
    bee_level            = Column(String(20), nullable=True)
    company_size         = Column(String(20), nullable=True)

    password_hash = Column(String(255), nullable=False)

    # Multi‑select preferences stored as JSON arrays of strings
    industry_preferences     = Column(JSON, nullable=True)
    province_preferences     = Column(JSON, nullable=True)
    town_preferences         = Column(JSON, nullable=True)
    municipality_preferences = Column(JSON, nullable=True)

    business_location = Column(String(500), nullable=True)
    business_lat      = Column(Float, nullable=True)
    business_lng      = Column(Float, nullable=True)
    search_radius_km  = Column(Integer, default=100, nullable=False)

    # Credit system — stored as Numeric(10,2) to avoid floating‑point errors
    credit_balance = Column(Numeric(10, 2), default=5.00, nullable=False)

    # Account lifecycle
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships — lazy="dynamic" returns a Query object for further filtering
    transactions = relationship("Transaction", back_populates="user", lazy="dynamic")
    search_logs  = relationship("SearchLog",   back_populates="user", lazy="dynamic")

    # --- Convenience properties (return [] instead of None) ---
    @property
    def industry_prefs(self):
        return self.industry_preferences or []

    @property
    def province_prefs(self):
        return self.province_preferences or []

    @property
    def town_prefs(self):
        return self.town_preferences or []

    @property
    def municipality_prefs(self):
        return self.municipality_preferences or []


# ------------------------------------------------------------------
# TENDER
# ------------------------------------------------------------------
class Tender(Base):
    """
    A single tender opportunity scraped from a government website.

    Uniqueness is enforced by `content_hash` (MD5 of title + source_url
    + closing_date). This prevents duplicate entries when the same
    tender is re‑scraped.

    Composite indexes speed up the two most common query patterns:
    1. Filter by province + industry (user dashboard/search).
    2. Filter by closing date + active status (expiry scans).
    3. Filter by active + scraped_at (latest tenders feed).
    """
    __tablename__ = "tenders"

    id                = Column(Integer, primary_key=True, index=True)
    title             = Column(String(500), nullable=False)
    description       = Column(Text, nullable=True)
    issuing_body      = Column(String(300), nullable=True)    # e.g., "City of Cape Town"
    province          = Column(String(100), nullable=True, index=True)
    municipality      = Column(String(200), nullable=True)
    town              = Column(String(200), nullable=True)
    industry_category = Column(String(200), nullable=True, index=True)

    # closing_date is the raw string; closing_date_parsed is the DateTime version
    closing_date        = Column(String(50), nullable=True)
    closing_date_parsed = Column(DateTime(timezone=True), nullable=True, index=True)
    posted_date         = Column(String(50), nullable=True)

    source_url       = Column(String(1000), nullable=False)  # link to the original listing
    source_site      = Column(String(200), nullable=True)    # domain (e.g., "joburg.org.za")
    reference_number = Column(String(200), nullable=True)
    contact_info     = Column(Text, nullable=True)

    # Deduplication key
    content_hash = Column(String(32), unique=True, index=True, nullable=False)

    document_url = Column(String(1000), nullable=True)  # direct PDF link if available

    # Geolocation — may be NULL if not detected
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    # Lifecycle timestamps
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active  = Column(Boolean, default=True, nullable=False, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_tenders_province_industry', 'province', 'industry_category'),
        Index('ix_tenders_closing_active', 'closing_date_parsed', 'is_active'),
        Index('ix_tenders_active_scraped', 'is_active', 'scraped_at'),
    )


# ------------------------------------------------------------------
# SEARCH LOG
# ------------------------------------------------------------------
class SearchLog(Base):
    """
    Immutable audit log of every search performed by a user.

    Stores the full query parameters as JSON so we can later analyse
    what users are searching for, and how many results each query
    returned.
    """
    __tablename__ = "search_logs"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    query_params    = Column(JSON, nullable=True)     # the full SearchRequest as a dict
    result_count    = Column(Integer, default=0, nullable=False)
    credits_charged = Column(Numeric(10, 2), default=0.00, nullable=False)
    searched_at     = Column(DateTime(timezone=True), server_default=func.now(),
                             nullable=False)

    # Back‑reference to the user who performed the search
    user = relationship("User", back_populates="search_logs")


# ------------------------------------------------------------------
# TRANSACTION
# ------------------------------------------------------------------
class Transaction(Base):
    """
    Immutable ledger of all credit movements.

    Each row represents either:
    - A credit (e.g., welcome bonus, top‑up)
    - A debit  (search cost)

    The `amount` is always positive; the type column distinguishes
    credit vs debit.
    """
    __tablename__ = "transactions"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    amount           = Column(Numeric(10, 2), nullable=False)
    transaction_type = Column(String(10), nullable=False)  # "credit" or "debit"
    description      = Column(String(500), nullable=True)  # human‑readable note
    created_at       = Column(DateTime(timezone=True), server_default=func.now(),
                              nullable=False)

    user = relationship("User", back_populates="transactions")


# ------------------------------------------------------------------
# SCRAPER STATUS
# ------------------------------------------------------------------
class ScraperStatus(Base):
    """
    Per‑source health tracking.

    After each scrape cycle, the engine upserts a row for every source.
    This allows the admin dashboard to show which sites are healthy and
    which are failing, along with the last error message.
    """
    __tablename__ = "scraper_status"

    id                = Column(Integer, primary_key=True, index=True)
    site_name         = Column(String(200), unique=True, nullable=False, index=True)
    last_scraped_at   = Column(DateTime(timezone=True), nullable=True)
    last_result_count = Column(Integer, default=0, nullable=False)
    last_error        = Column(Text, nullable=True)
    is_healthy        = Column(Boolean, default=True, nullable=False, index=True)


# ------------------------------------------------------------------
# CRAWL RESULT
# ------------------------------------------------------------------
class CrawlResult(Base):
    """
    A single URL discovered by the BFS crawler.

    Each row represents one page that the crawler visited and deemed
    to contain tender information. After the scraper processes it,
    `scraped_at` and `scrape_success` are updated.

    Deduplication is handled via `url_hash` (MD5 of the discovered URL).
    """
    __tablename__ = "crawl_results"

    id             = Column(Integer, primary_key=True, index=True)
    site_name      = Column(String(200), nullable=False, index=True)
    seed_url       = Column(String(1000), nullable=False)    # the page the crawl started from
    discovered_url = Column(String(1000), nullable=False)    # the actual URL found
    final_url      = Column(String(1000), nullable=True)     # after redirects
    url_hash       = Column(String(32), unique=True, index=True, nullable=False)
    depth          = Column(Integer, default=0, nullable=False)  # BFS depth
    status_code    = Column(Integer, default=200, nullable=False)

    # Lifecycle
    is_active     = Column(Boolean, default=True, nullable=False, index=True)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now(),
                           nullable=False)
    last_seen_at  = Column(DateTime(timezone=True), server_default=func.now(),
                           onupdate=func.now())

    # Scraping outcome
    scraped_at     = Column(DateTime(timezone=True), nullable=True)
    scrape_success = Column(Boolean, default=False, nullable=False)
    scrape_error   = Column(Text, nullable=True)
    tenders_found  = Column(Integer, default=0, nullable=False)

    # Indexes for efficient filtering of pending URLs and per‑site queries
    __table_args__ = (
        Index('ix_crawl_results_pending_scrape', 'is_active', 'scraped_at'),
        Index('ix_crawl_results_site_active', 'site_name', 'is_active'),
    )