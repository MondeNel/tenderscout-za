from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, JSON
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    industry_preferences = Column(JSON, default=[])
    province_preferences = Column(JSON, default=[])
    town_preferences = Column(JSON, default=[])
    credit_balance = Column(Float, default=5.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    issuing_body = Column(String, nullable=True)
    province = Column(String, nullable=True)
    town = Column(String, nullable=True)
    industry_category = Column(String, nullable=True)
    closing_date = Column(String, nullable=True)
    posted_date = Column(String, nullable=True)
    source_url = Column(String, nullable=False)
    source_site = Column(String, nullable=True)
    reference_number = Column(String, nullable=True)
    contact_info = Column(Text, nullable=True)
    content_hash = Column(String, unique=True, index=True)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    query_params = Column(JSON, default={})
    result_count = Column(Integer, default=0)
    credits_charged = Column(Float, default=0.0)
    searched_at = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ScraperStatus(Base):
    __tablename__ = "scraper_status"

    id = Column(Integer, primary_key=True, index=True)
    site_name = Column(String, unique=True, nullable=False)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    last_result_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    is_healthy = Column(Boolean, default=True)
