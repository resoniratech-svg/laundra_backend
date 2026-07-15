from pydantic import BaseModel, EmailStr
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime

class CustomerBase(BaseModel):
    name: Optional[str] = None
    phone: str
    email: Optional[EmailStr] = None
    address: Optional[str] = None

class CustomerCreate(CustomerBase):
    otp: Optional[str] = ""
    password: Optional[str] = "customer123"

class CustomerOut(CustomerBase):
    id: UUID
    tenant_id: UUID
    wallet_balance: Decimal
    loyalty_points: int
    qr_status: str
    created_at: datetime

    class Config:
        from_attributes = True

class CustomerLogin(BaseModel):
    phone: str
    tenant_id: UUID
