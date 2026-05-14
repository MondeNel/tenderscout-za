from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text,
    Boolean, JSON, Index, ForeignKey, Numeric, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableList, MutableDict
from database import Base

# =============================================================================
# USER MODEL
# =============================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Use MutableList.as_mutable(JSON) so changes like .append() are detected
    industry_preferences = Column(MutableList.as_mutable(JSON), nullable=True, server_default=text("'[]'"))
    province_preferences = Column(MutableList.as_mutable(JSON), nullable=True, server_default=text("'[]'"))
    town_preferences = Column(MutableList.as_mutable(JSON), nullable=True, server_default=text("'[]'"))
    municipality_preferences = Column(MutableList.as_mutable(JSON), nullable=True, server_default=text("'[]'"))

    business_location = Column(String(500), nullable=True)
    business_lat = Column(Float, nullable=True)
    business_lng = Column(Float, nullable=True)
    search_radius_km = Column(Integer, default=100, nullable=False)

    credit_balance = Column(Numeric(10, 2), default=5.00, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships - Removed lazy="dynamic" for better performance in most FastAPI cases
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    search_logs = relationship("SearchLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"

# =============================================================================
# TENDER MODEL
# =============================================================================
class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    issuing_body = Column(String(300), nullable=True, index=True)
    
    # Location data
    province = Column(String(100), nullable=True, index=True)
    municipality = Column(String(200), nullable=True, index=True)
    town = Column(String(200), nullable=True, index=True)
    industry_category = Column(String(200), nullable=True, index=True)

    # Date handling
    closing_date = Column(String(50), nullable=True) # Scraped string
    closing_date_parsed = Column(DateTime(timezone=True), nullable=True, index=True)
    posted_date = Column(String(50), nullable=True)
    
    source_url = Column(String(1000), nullable=False)
    source_site = Column(String(200), nullable=True, index=True)
    reference_number = Column(String(200), nullable=True, index=True)
    
    content_hash = Column(String(32), unique=True, index=True, nullable=False)
    document_url = Column(String(1000), nullable=True)

    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        Index('ix_tenders_location_search', 'province', 'municipality', 'town'),
        Index('ix_tenders_active_closing', 'is_active', 'closing_date_parsed'),
        # Optimization: Covering index for the search dashboard
        Index('ix_tenders_summary', 'is_active', 'scraped_at', 'province', 'industry_category'),
    )

# =============================================================================
# LOGGING & TRACKING
# =============================================================================
class SearchLog(Base):
    __tablename__ = "search_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query_params = Column(MutableDict.as_mutable(JSON), nullable=True)
    result_count = Column(Integer, default=0)
    credits_charged = Column(Numeric(10, 2), default=0.00)
    searched_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="search_logs")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_type = Column(String(20), nullable=False) # Increased length for safety
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")

class ScraperStatus(Base):
    __tablename__ = "scraper_status"
    id = Column(Integer, primary_key=True)
    site_name = Column(String(200), unique=True, nullable=False)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    last_result_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    is_healthy = Column(Boolean, default=True, index=True)

class CrawlResult(Base):
    __tablename__ = "crawl_results"
    id = Column(Integer, primary_key=True, index=True)
    site_name = Column(String(200), nullable=False, index=True)
    discovered_url = Column(String(1000), nullable=False)
    url_hash = Column(String(32), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    scraped_at = Column(DateTime(timezone=True), nullable=True, index=True)
    scrape_success = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('ix_crawl_pending', 'site_name', 'is_active', 'scraped_at'),
    )