from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import datetime


# =============================================================================
# SHARED CONFIG
# =============================================================================
# All ORM-backed schemas inherit this so we don't repeat model_config everywhere.
# Decimal values are converted to float via field validators, not json_encoders,
# because json_encoders was removed in Pydantic v2.

class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# AUTHENTICATION SCHEMAS
# =============================================================================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email:             EmailStr
    full_name:         str
    password:          str
    province:          Optional[str]   = None
    town:              Optional[str]   = None
    business_location: Optional[str]   = None
    business_lat:      Optional[float] = None
    business_lng:      Optional[float] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be blank")
        return v

    @field_validator("business_lat")
    @classmethod
    def validate_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("business_lng")
    @classmethod
    def validate_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserOut(_OrmBase):
    id:                      int
    email:                   str
    full_name:               str
    credit_balance:          float
    industry_preferences:    List[str] = []
    province_preferences:    List[str] = []
    town_preferences:        List[str] = []
    municipality_preferences:List[str] = []
    business_location:       Optional[str]   = None
    business_lat:            Optional[float] = None
    business_lng:            Optional[float] = None
    search_radius_km:        int             = 100
    created_at:              datetime

    # ── FIX: Coerce None → [] BEFORE list validation (mode="before") ──────
    @field_validator("industry_preferences", "province_preferences",
                     "town_preferences", "municipality_preferences",
                     mode="before")
    @classmethod
    def none_to_empty_list(cls, v):
        """SQLite stores JSON nulls — turn them into empty lists."""
        if v is None:
            return []
        return v

    # ── FIX: Decimal → float BEFORE validation (mode="before") ────────────
    @field_validator("credit_balance", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        if isinstance(v, Decimal):
            return float(v)
        return v


# =============================================================================
# USER PREFERENCES
# =============================================================================

class UserPreferences(BaseModel):
    industry_preferences:     Optional[List[str]]  = None
    province_preferences:     Optional[List[str]]  = None
    town_preferences:         Optional[List[str]]  = None
    municipality_preferences: Optional[List[str]]  = None
    business_location:        Optional[str]         = None
    business_lat:             Optional[float]       = None
    business_lng:             Optional[float]       = None
    search_radius_km:         Optional[int]         = None

    @field_validator("business_lat")
    @classmethod
    def validate_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("business_lng")
    @classmethod
    def validate_lng(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("search_radius_km")
    @classmethod
    def validate_radius(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 1000):
            raise ValueError("search_radius_km must be between 1 and 1000")
        return v


# =============================================================================
# CREDIT / PAYMENT SCHEMAS
# =============================================================================

class CreditBalance(BaseModel):
    balance:    float
    rand_value: float


class TopUpRequest(BaseModel):
    package: Literal["100", "250", "500"]


class TopUpResponse(BaseModel):
    success:       bool
    credits_added: float
    new_balance:   float
    message:       str


# =============================================================================
# TENDER SCHEMAS
# =============================================================================

class TenderOut(_OrmBase):
    id:                int
    title:             str
    description:       Optional[str]      = None
    issuing_body:      Optional[str]      = None
    province:          Optional[str]      = None
    municipality:      Optional[str]      = None
    town:              Optional[str]      = None
    industry_category: Optional[str]      = None
    closing_date:      Optional[str]      = None
    posted_date:       Optional[str]      = None
    source_url:        str
    source_site:       Optional[str]      = None
    reference_number:  Optional[str]      = None
    contact_info:      Optional[str]      = None
    document_url:      Optional[str]      = None
    is_active:         bool               = True
    scraped_at:        Optional[datetime] = None
    lat:               Optional[float]    = None
    lng:               Optional[float]    = None


class TenderLatestResponse(BaseModel):
    new_count: int
    tenders:   List[TenderOut]


class TenderStatsResponse(BaseModel):
    total_tenders:   int
    active_tenders:  int
    expired_tenders: int
    by_province:     dict
    by_industry:     dict
    by_municipality: dict
    last_updated:    Optional[datetime] = None


# =============================================================================
# SEARCH SCHEMAS
# =============================================================================

class SearchRequest(BaseModel):
    industries:     List[str]       = []
    provinces:      List[str]       = []
    municipalities: List[str]       = []
    towns:          List[str]       = []
    keyword:        Optional[str]   = None
    user_lat:       Optional[float] = None
    user_lng:       Optional[float] = None
    radius_km:      Optional[float] = None
    page:           int             = 1
    page_size:      int             = 20

    @field_validator("page")
    @classmethod
    def page_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("page must be >= 1")
        return v

    @field_validator("page_size")
    @classmethod
    def page_size_range(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("page_size must be between 1 and 100")
        return v

    @field_validator("keyword")
    @classmethod
    def keyword_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @field_validator("radius_km")
    @classmethod
    def radius_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("radius_km must be positive")
        return v

    @model_validator(mode="after")
    def radius_requires_coords(self) -> "SearchRequest":
        if self.radius_km is not None:
            if self.user_lat is None or self.user_lng is None:
                self.radius_km = None
        return self


class SearchResponse(BaseModel):
    total:           int
    page:            int
    page_size:       int
    results:         List[TenderOut]
    credits_charged: float


# =============================================================================
# TRANSACTION SCHEMAS
# =============================================================================

class TransactionOut(_OrmBase):
    id:               int
    amount:           float
    transaction_type: str
    description:      Optional[str] = None
    created_at:       datetime


# =============================================================================
# SCRAPER STATUS SCHEMAS
# =============================================================================

class ScraperStatusOut(_OrmBase):
    id:                int
    site_name:         str
    last_scraped_at:   Optional[datetime] = None
    last_result_count: int                = 0
    last_error:        Optional[str]      = None
    is_healthy:        bool               = True


class ScraperStatusSummary(BaseModel):
    total_sources:     int
    healthy_sources:   int
    unhealthy_sources: int
    sources:           List[ScraperStatusOut]
    last_full_run:     Optional[datetime] = None


class ScraperRunResponse(BaseModel):
    success:       bool
    new_tenders:   int
    total_scraped: int
    sources_run:   int
    errors:        List[str] = []
    run_at:        datetime


# =============================================================================
# CRAWLER SCHEMAS
# =============================================================================

class CrawlResultOut(_OrmBase):
    id:             int
    site_name:      str
    seed_url:       str
    discovered_url: str
    final_url:      Optional[str]      = None
    depth:          int
    status_code:    int
    is_active:      bool
    discovered_at:  datetime
    last_seen_at:   Optional[datetime] = None
    scraped_at:     Optional[datetime] = None
    scrape_success: bool               = False
    scrape_error:   Optional[str]      = None
    tenders_found:  int                = 0


class CrawlStatsResponse(BaseModel):
    total_urls:     int
    active_urls:    int
    pending_scrape: int
    scraped_urls:   int
    failed_scrapes: int
    by_site:        dict


class PendingCrawlUrlsResponse(BaseModel):
    total: int
    urls:  List[CrawlResultOut]


# =============================================================================
# DASHBOARD / ADMIN SCHEMAS
# =============================================================================

class DashboardStatsResponse(BaseModel):
    total_users:    int
    active_users:   int
    total_tenders:  int
    active_tenders: int
    total_searches: int
    total_revenue:  float
    scraper_health: ScraperStatusSummary
    crawler_stats:  CrawlStatsResponse
    recent_tenders: List[TenderOut]
    recent_searches:List[dict]


class HealthCheckResponse(BaseModel):
    status:    str
    database:  bool
    scrapers:  ScraperStatusSummary
    crawlers:  CrawlStatsResponse
    timestamp: datetime


# =============================================================================
# REFERENCE DATA SCHEMAS
# =============================================================================

class ProvinceOut(BaseModel):
    name:               str
    municipality_count: int
    tender_count:       int


class MunicipalityOut(BaseModel):
    name:         str
    province:     str
    tender_count: int


class TownOut(BaseModel):
    name:         str
    municipality: str
    province:     str
    tender_count: int


class IndustryOut(BaseModel):
    name:         str
    tender_count: int


class ReferenceDataResponse(BaseModel):
    provinces:     List[ProvinceOut]
    municipalities:List[MunicipalityOut]
    towns:         List[TownOut]
    industries:    List[IndustryOut]
    last_updated:  datetime


# =============================================================================
# SEARCH HISTORY SCHEMA
# =============================================================================

class SearchHistoryOut(_OrmBase):
    id:              int
    query_params:    dict              = {}
    result_count:    int               = 0
    credits_charged: float
    searched_at:     datetime