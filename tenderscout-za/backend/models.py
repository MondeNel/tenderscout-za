from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Index, Integer, Numeric, String, Text, JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    full_name     = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Stored as JSON arrays — use the _prefs() helper to read safely
    industry_preferences     = Column(JSON, nullable=True)
    province_preferences     = Column(JSON, nullable=True)
    town_preferences         = Column(JSON, nullable=True)
    municipality_preferences = Column(JSON, nullable=True)

    # Business location
    business_location = Column(String(500), nullable=True)
    business_lat      = Column(Float, nullable=True)
    business_lng      = Column(Float, nullable=True)
    search_radius_km  = Column(Integer, default=100, nullable=False)

    # Numeric avoids float rounding errors on financial values
    credit_balance = Column(Numeric(10, 2), default=5.00, nullable=False)

    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    transactions = relationship("Transaction", back_populates="user", lazy="dynamic")
    search_logs  = relationship("SearchLog",   back_populates="user", lazy="dynamic")

    # Single helper — avoids four identical @property definitions
    def _prefs(self, field: str) -> list:
        return getattr(self, field) or []

    @property
    def industry_prefs(self):     return self._prefs("industry_preferences")
    @property
    def province_prefs(self):     return self._prefs("province_preferences")
    @property
    def town_prefs(self):         return self._prefs("town_preferences")
    @property
    def municipality_prefs(self): return self._prefs("municipality_preferences")

    def __repr__(self):
        return f"<User id={self.id} email={self.email} balance={self.credit_balance}>"


# ---------------------------------------------------------------------------
# Tender
# ---------------------------------------------------------------------------

class Tender(Base):
    __tablename__ = "tenders"

    id               = Column(Integer, primary_key=True, index=True)
    title            = Column(String(500), nullable=False)
    description      = Column(Text, nullable=True)
    issuing_body     = Column(String(300), nullable=True)
    province         = Column(String(100), nullable=True, index=True)
    municipality     = Column(String(200), nullable=True)
    town             = Column(String(200), nullable=True)
    industry_category= Column(String(200), nullable=True, index=True)

    # closing_date kept as String (scraped format: DD/MM/YYYY) +
    # closing_date_parsed for filtering/sorting
    closing_date        = Column(String(50), nullable=True)
    closing_date_parsed = Column(DateTime(timezone=True), nullable=True, index=True)
    posted_date         = Column(String(50), nullable=True)

    source_url       = Column(String(1000), nullable=False)
    source_site      = Column(String(200), nullable=True)
    reference_number = Column(String(200), nullable=True)
    contact_info     = Column(Text, nullable=True)

    # MD5(title + issuing_body + closing_date) — deduplication key
    content_hash = Column(String(32), unique=True, index=True, nullable=False)

    document_url = Column(String(1000), nullable=True)
    lat          = Column(Float, nullable=True)
    lng          = Column(Float, nullable=True)

    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active  = Column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        Index("ix_tenders_province_industry", "province", "industry_category"),
        Index("ix_tenders_closing_active",    "closing_date_parsed", "is_active"),
        Index("ix_tenders_active_scraped",    "is_active", "scraped_at"),
    )

    def __repr__(self):
        return f"<Tender id={self.id} title={self.title[:40]!r} province={self.province}>"


# ---------------------------------------------------------------------------
# Search Log
# ---------------------------------------------------------------------------

class SearchLog(Base):
    __tablename__ = "search_logs"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query_params    = Column(JSON, nullable=True)
    result_count    = Column(Integer, default=0, nullable=False)
    credits_charged = Column(Numeric(10, 2), default=0.00, nullable=False)
    searched_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="search_logs")

    def __repr__(self):
        return f"<SearchLog id={self.id} user_id={self.user_id} results={self.result_count}>"


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class Transaction(Base):
    __tablename__ = "transactions"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount           = Column(Numeric(10, 2), nullable=False)
    transaction_type = Column(String(10), nullable=False)  # "credit" | "debit"
    description      = Column(String(500), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction id={self.id} user_id={self.user_id} {self.transaction_type} {self.amount}>"


# ---------------------------------------------------------------------------
# Scraper Status
# ---------------------------------------------------------------------------

class ScraperStatus(Base):
    __tablename__ = "scraper_status"

    id                = Column(Integer, primary_key=True, index=True)
    site_name         = Column(String(200), unique=True, nullable=False, index=True)
    last_scraped_at   = Column(DateTime(timezone=True), nullable=True)
    last_result_count = Column(Integer, default=0, nullable=False)
    last_error        = Column(Text, nullable=True)
    is_healthy        = Column(Boolean, default=True, nullable=False, index=True)

    def __repr__(self):
        return f"<ScraperStatus site={self.site_name} healthy={self.is_healthy}>"


# ---------------------------------------------------------------------------
# Crawl Result
# ---------------------------------------------------------------------------

class CrawlResult(Base):
    """URLs discovered by the BFS crawler, queued for detailed scraping."""
    __tablename__ = "crawl_results"

    id   = Column(Integer, primary_key=True, index=True)

    site_name = Column(String(200), nullable=False, index=True)
    seed_url  = Column(String(1000), nullable=False)

    discovered_url = Column(String(1000), nullable=False)
    final_url      = Column(String(1000), nullable=True)
    url_hash       = Column(String(32), unique=True, index=True, nullable=False)

    depth       = Column(Integer, default=0, nullable=False)
    status_code = Column(Integer, default=200, nullable=False)
    is_active   = Column(Boolean, default=True, nullable=False, index=True)

    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    scraped_at     = Column(DateTime(timezone=True), nullable=True)
    scrape_success = Column(Boolean, default=False, nullable=False)
    scrape_error   = Column(Text, nullable=True)
    tenders_found  = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_crawl_results_pending_scrape", "is_active", "scraped_at"),
        Index("ix_crawl_results_site_active",    "site_name", "is_active"),
    )

    def __repr__(self):
        return f"<CrawlResult id={self.id} site={self.site_name} url={self.discovered_url[:60]!r}>"