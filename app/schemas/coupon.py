from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import date, datetime

class CouponBase(BaseModel):
    code: Optional[str] = None
    discount_type: Optional[str] = None  # PERCENTAGE | FLAT
    value: Optional[Decimal] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    required_services: Optional[list] = None

class CouponCreate(CouponBase):
    code: str
    discount_type: str
    value: Decimal
    start_date: date
    expiry_date: date

class CouponOut(CouponBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
