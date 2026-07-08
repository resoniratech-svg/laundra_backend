from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime

class ServiceBase(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[Decimal] = None  # Normal price
    express_price: Optional[Decimal] = None  # Express price (higher)
    unit: Optional[str] = None  # KG / PIECE
    image_url: Optional[str] = None

class ServiceCreate(ServiceBase):
    tenant_id: UUID
    name: str
    category: str
    price: Decimal
    unit: str

class ServiceOut(ServiceBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
