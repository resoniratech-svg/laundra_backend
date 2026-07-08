from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime

class PaymentCreate(BaseModel):
    order_id: UUID
    amount: Decimal
    method: str  # CASH, UPI, CARD, WALLET
    delivery_boy_id: Optional[UUID] = None
    delivery_boy_commission: Optional[Decimal] = None

class PaymentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_id: UUID
    amount: Decimal
    method: str
    status: str
    delivery_boy_id: Optional[UUID]
    delivery_boy_commission: Optional[Decimal]
    created_at: datetime

    class Config:
        from_attributes = True
