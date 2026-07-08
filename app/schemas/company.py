from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class CompanyBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    subdomain: Optional[str] = None
    logo: Optional[str] = None
    address: Optional[str] = None

class CompanyCreate(CompanyBase):
    password: str

class CompanyOut(CompanyBase):
    id: UUID
    status: str
    delivery_commission_percent: float = 0.0
    created_at: datetime

    class Config:
        from_attributes = True

class CompanySettingsUpdate(BaseModel):
    delivery_commission_percent: Optional[float] = None
