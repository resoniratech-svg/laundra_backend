from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from uuid import UUID
from datetime import datetime

class OrderItemBase(BaseModel):
    service_id: UUID
    quantity: int

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemOut(OrderItemBase):
    id: UUID
    order_id: UUID
    price: Decimal

    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    customer_id: UUID

class OrderCreate(OrderBase):
    items: List[OrderItemCreate]
    coupon_code: Optional[str] = None
    is_express: bool = False

class OrderOut(OrderBase):
    id: UUID
    tenant_id: UUID
    order_number: str
    status: str
    total_amount: Decimal
    discount: Decimal
    paid_amount: Decimal
    payment_status: str
    qr_code: Optional[str] = None
    rating: Optional[int] = None
    review: Optional[str] = None
    review_reply: Optional[str] = None
    review_hidden: bool = False
    pickup_address: Optional[str] = None
    delivery_address: Optional[str] = None
    special_instructions: Optional[str] = None
    is_express: bool = False
    pickup_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    created_at: datetime
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True

class OrderReviewPayload(BaseModel):
    rating: int
    review: Optional[str] = None

class ReviewReplyPayload(BaseModel):
    reply: str

class ReviewVisibilityPayload(BaseModel):
    is_hidden: bool
