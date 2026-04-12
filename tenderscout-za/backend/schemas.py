from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserPreferences(BaseModel):
    industry_preferences: List[str] = []
    province_preferences: List[str] = []
    town_preferences: List[str] = []


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    industry_preferences: List[str] = []
    province_preferences: List[str] = []
    town_preferences: List[str] = []
    credit_balance: float
    created_at: datetime

    class Config:
        from_attributes = True


class TenderOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    issuing_body: Optional[str]
    province: Optional[str]
    town: Optional[str]
    industry_category: Optional[str]
    closing_date: Optional[str]
    posted_date: Optional[str]
    source_url: str
    source_site: Optional[str]
    reference_number: Optional[str]
    document_url: Optional[str]
    scraped_at: datetime

    class Config:
        from_attributes = True


class TenderLatestResponse(BaseModel):
    new_count: int
    tenders: List[TenderOut]


class SearchRequest(BaseModel):
    industries: List[str] = []
    provinces: List[str] = []
    towns: List[str] = []
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 10


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[TenderOut]
    credits_charged: float


class TopUpRequest(BaseModel):
    package: str


class TopUpResponse(BaseModel):
    success: bool
    credits_added: float
    new_balance: float
    message: str


class CreditBalance(BaseModel):
    balance: float
    rand_value: float


class TransactionOut(BaseModel):
    id: int
    amount: float
    transaction_type: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ScraperStatusOut(BaseModel):
    site_name: str
    last_scraped_at: Optional[datetime]
    last_result_count: int
    last_error: Optional[str]
    is_healthy: bool

    class Config:
        from_attributes = True
