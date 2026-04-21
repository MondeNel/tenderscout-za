from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime


# =============================================================================
# AUTHENTICATION SCHEMAS
# =============================================================================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    credit_balance: float
    industry_preferences: List[str] = []
    province_preferences: List[str] = []
    town_preferences: List[str] = []
    municipality_preferences: List[str] = []
    business_location: Optional[str] = None
    business_lat: Optional[float] = None
    business_lng: Optional[float] = None
    search_radius_km: Optional[int] = 100
    created_at: datetime


class UserPreferences(BaseModel):
    industry_preferences: List[str] = []
    province_preferences: List[str] = []
    town_preferences: List[str] = []
    municipality_preferences: List[str] = []
    business_location: Optional[str] = None
    business_lat: Optional[float] = None
    business_lng: Optional[float] = None
    search_radius_km: Optional[int] = 100


# =============================================================================
# CREDIT/PAYMENT SCHEMAS
# =============================================================================

class CreditBalance(BaseModel):
    balance: float
    rand_value: float


class TopUpRequest(BaseModel):
    package: str


class TopUpResponse(BaseModel):
    success: bool
    credits_added: float
    new_balance: float
    message: str


# =============================================================================
# TENDER SCHEMAS
# =============================================================================

class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: Optional[str] = None
    issuing_body: Optional[str] = None
    province: Optional[str] = None
    municipality: Optional[str] = None
    town: Optional[str] = None
    industry_category: Optional[str] = None
    closing_date: Optional[str] = None
    posted_date: Optional[str] = None
    source_url: str
    source_site: Optional[str] = None
    reference_number: Optional[str] = None
    contact_info: Optional[str] = None
    document_url: Optional[str] = None
    is_active: Optional[bool] = True
    scraped_at: Optional[datetime] = None


class TenderLatestResponse(BaseModel):
    new_count: int
    tenders: List[TenderOut]


class TenderStatsResponse(BaseModel):
    """Statistics about tenders in the database."""
    total_tenders: int
    active_tenders: int
    expired_tenders: int
    by_province: dict
    by_industry: dict
    by_municipality: dict
    last_updated: Optional[datetime] = None


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
    radius_km:      Optional[float] = 100
    page:           int             = 1
    page_size:      int             = 20


class SearchResponse(BaseModel):
    total:           int
    page:            int
    page_size:       int
    results:         List[TenderOut]
    credits_charged: float


# =============================================================================
# TRANSACTION SCHEMAS
# =============================================================================

class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amount: float
    transaction_type: str
    description: Optional[str] = None
    created_at: datetime


# =============================================================================
# SCRAPER STATUS SCHEMAS
# =============================================================================

class ScraperStatusOut(BaseModel):
    """Status of a single scraper source."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_name: str
    last_scraped_at: Optional[datetime] = None
    last_result_count: int = 0
    last_error: Optional[str] = None
    is_healthy: bool = True


class ScraperStatusSummary(BaseModel):
    """Summary of all scraper sources."""
    total_sources: int
    healthy_sources: int
    unhealthy_sources: int
    sources: List[ScraperStatusOut]
    last_full_run: Optional[datetime] = None


class ScraperRunResponse(BaseModel):
    """Response after running the scraper pipeline."""
    success: bool
    new_tenders: int
    total_scraped: int
    sources_run: int
    errors: List[str] = []
    run_at: datetime


# =============================================================================
# CRAWLER SCHEMAS (NEW)
# =============================================================================

class CrawlResultOut(BaseModel):
    """Discovered URL from the BFS crawler."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_name: str
    seed_url: str
    discovered_url: str
    final_url: Optional[str] = None
    depth: int
    status_code: int
    is_active: bool
    discovered_at: datetime
    last_seen_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    scrape_success: bool = False
    scrape_error: Optional[str] = None
    tenders_found: int = 0


class CrawlStatsResponse(BaseModel):
    """Statistics about crawled URLs."""
    total_urls: int
    active_urls: int
    pending_scrape: int  # URLs discovered but not yet scraped
    scraped_urls: int
    failed_scrapes: int
    by_site: dict  # site_name -> count


class PendingCrawlUrlsResponse(BaseModel):
    """List of URLs that need to be scraped."""
    total: int
    urls: List[CrawlResultOut]


# =============================================================================
# DASHBOARD/ADMIN SCHEMAS
# =============================================================================

class DashboardStatsResponse(BaseModel):
    """Overall platform statistics for admin dashboard."""
    total_users: int
    active_users: int
    total_tenders: int
    active_tenders: int
    total_searches: int
    total_revenue: float
    scraper_health: ScraperStatusSummary
    crawler_stats: CrawlStatsResponse
    recent_tenders: List[TenderOut]
    recent_searches: List[dict]  # Simplified search log entries


class HealthCheckResponse(BaseModel):
    """System health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    database: bool
    scrapers: ScraperStatusSummary
    crawlers: CrawlStatsResponse
    timestamp: datetime


# =============================================================================
# MUNICIPALITY/PROVINCE REFERENCE SCHEMAS
# =============================================================================

class ProvinceOut(BaseModel):
    """Province reference data."""
    name: str
    municipality_count: int
    tender_count: int


class MunicipalityOut(BaseModel):
    """Municipality reference data."""
    name: str
    province: str
    tender_count: int


class TownOut(BaseModel):
    """Town reference data."""
    name: str
    municipality: str
    province: str
    tender_count: int


class IndustryOut(BaseModel):
    """Industry category reference data."""
    name: str
    tender_count: int


class ReferenceDataResponse(BaseModel):
    """All reference data for frontend filters."""
    provinces: List[ProvinceOut]
    municipalities: List[MunicipalityOut]
    towns: List[TownOut]
    industries: List[IndustryOut]
    last_updated: datetime