from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime


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
    created_at: datetime

class UserPreferences(BaseModel):
    industry_preferences: List[str] = []
    province_preferences: List[str] = []
    town_preferences: List[str] = []

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
    document_url: Optional[str] = None
    scraped_at: datetime

class TenderLatestResponse(BaseModel):
    new_count: int
    tenders: List[TenderOut]

class SearchRequest(BaseModel):
    industries: List[str] = []
    provinces: List[str] = []
    municipalities: List[str] = []
    towns: List[str] = []
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 20

class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[TenderOut]
    credits_charged: float

class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amount: float
    transaction_type: str
    description: Optional[str] = None
    created_at: datetime
