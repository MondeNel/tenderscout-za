from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON, Index
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"
    id                       = Column(Integer, primary_key=True, index=True)
    email                    = Column(String, unique=True, index=True, nullable=False)
    full_name                = Column(String, nullable=False)
    password_hash            = Column(String, nullable=False)
    industry_preferences     = Column(JSON, default=list)
    province_preferences     = Column(JSON, default=list)
    town_preferences         = Column(JSON, default=list)
    municipality_preferences = Column(JSON, default=list)
    business_location        = Column(String, nullable=True)
    business_lat             = Column(Float, nullable=True)
    business_lng             = Column(Float, nullable=True)
    search_radius_km         = Column(Integer, default=100)
    credit_balance           = Column(Float, default=5.0)
    is_active                = Column(Boolean, default=True)
    created_at               = Column(DateTime(timezone=True), server_default=func.now())
    updated_at               = Column(DateTime(timezone=True), onupdate=func.now())


class Tender(Base):
    __tablename__ = "tenders"
    id               = Column(Integer, primary_key=True, index=True)
    title            = Column(String, nullable=False)
    description      = Column(Text, nullable=True)
    issuing_body     = Column(String, nullable=True)
    province         = Column(String, nullable=True, index=True)  # Added index for filtering
    municipality     = Column(String, nullable=True)
    town             = Column(String, nullable=True)
    industry_category= Column(String, nullable=True, index=True)  # Added index for filtering
    closing_date     = Column(String, nullable=True)
    posted_date      = Column(String, nullable=True)
    source_url       = Column(String, nullable=False)
    source_site      = Column(String, nullable=True)
    reference_number = Column(String, nullable=True)
    contact_info     = Column(Text, nullable=True)
    content_hash     = Column(String(32), unique=True, index=True, nullable=False)  # Added length
    document_url     = Column(String, nullable=True)
    scraped_at       = Column(DateTime(timezone=True), server_default=func.now())
    is_active        = Column(Boolean, default=True, index=True)  # Added index
    
    # Composite index for common filtered queries
    __table_args__ = (
        Index('ix_tenders_province_industry', 'province', 'industry_category'),
        Index('ix_tenders_closing_active', 'closing_date', 'is_active'),
    )


class SearchLog(Base):
    __tablename__ = "search_logs"
    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, nullable=False, index=True)
    query_params    = Column(JSON, default=dict)
    result_count    = Column(Integer, default=0)
    credits_charged = Column(Float, default=0.0)
    searched_at     = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, nullable=False, index=True)
    amount           = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)
    description      = Column(String, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())


class ScraperStatus(Base):
    __tablename__ = "scraper_status"
    id                = Column(Integer, primary_key=True, index=True)
    site_name         = Column(String, unique=True, nullable=False, index=True)
    last_scraped_at   = Column(DateTime(timezone=True), nullable=True)
    last_result_count = Column(Integer, default=0)
    last_error        = Column(Text, nullable=True)
    is_healthy        = Column(Boolean, default=True, index=True)


class CrawlResult(Base):
    """
    Stores URLs discovered by the BFS crawler.
    
    These URLs are candidates for detailed scraping. The scraper pipeline
    should query this table for active, unscraped URLs and extract full
    tender details from them.
    """
    __tablename__ = "crawl_results"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Source information
    site_name = Column(String(200), nullable=False, index=True)
    seed_url = Column(String(500), nullable=False)
    
    # URL information
    discovered_url = Column(String(500), nullable=False)
    final_url = Column(String(500), nullable=True)  # ← ADDED: URL after redirects
    url_hash = Column(String(32), unique=True, index=True, nullable=False)
    
    # Crawl metadata
    depth = Column(Integer, default=0)
    status_code = Column(Integer, default=200)
    
    # Status flags
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Scrape tracking — for pipeline integration
    scraped_at = Column(DateTime(timezone=True), nullable=True)  # ← ADDED: When this URL was scraped
    scrape_success = Column(Boolean, default=False)  # ← ADDED: Whether scraping succeeded
    scrape_error = Column(Text, nullable=True)  # ← ADDED: Error message if scraping failed
    tenders_found = Column(Integer, default=0)  # ← ADDED: Number of tenders extracted
    
    # Indexes for common queries
    __table_args__ = (
        # For finding URLs that need to be scraped
        Index('ix_crawl_results_pending_scrape', 'is_active', 'scraped_at'),
        # For site-specific queries
        Index('ix_crawl_results_site_active', 'site_name', 'is_active'),
    )