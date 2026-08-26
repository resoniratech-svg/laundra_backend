from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime

class DeliveryCreate(BaseModel):
    order_id: str
    delivery_boy_id: Optional[str] = None
    courier_name: Optional[str] = None
    type: str  # PICKUP / DELIVERY
    pickup_commission: Optional[Decimal] = Decimal('0.0')
    delivery_commission: Optional[Decimal] = Decimal('0.0')

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
    pickup_commission: Optional[Decimal] = Decimal('0.0')
    delivery_commission: Optional[Decimal] = Decimal('0.0')
    pickup_commission_paid: Optional[bool] = False
    delivery_commission_paid: Optional[bool] = False
    pickup_payment_method: Optional[str] = None
    delivery_payment_method: Optional[str] = None

    class Config:
        from_attributes = True
