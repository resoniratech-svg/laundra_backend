from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class DeliveryCreate(BaseModel):
    order_id: UUID
    delivery_boy_id: Optional[UUID] = None
    type: str  # PICKUP / DELIVERY

class DeliveryOut(BaseModel):
    id: UUID
    tenant_id: UUID
    order_id: UUID
    delivery_boy_id: Optional[UUID] = None
    type: str
    status: str  # ASSIGNED, PICKED, DELIVERED
    otp: Optional[str] = None
    delivered_at: Optional[datetime] = None
    photos: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True
