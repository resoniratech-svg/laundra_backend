from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from uuid import UUID
from datetime import datetime


# ── Profile ──────────────────────────────────────────────
class CustomerProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    profile_photo: Optional[str] = None

class CustomerProfileOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    wallet_balance: Decimal
    loyalty_points: int
    referral_code: Optional[str]
    profile_photo: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Password ─────────────────────────────────────────────
class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordPayload(BaseModel):
    email: str

class ResetPasswordPayload(BaseModel):
    email: str
    otp: str
    new_password: str


# ── Orders ───────────────────────────────────────────────
class CustomerOrderItemCreate(BaseModel):
    service_id: UUID
    quantity: int = 1

class CustomerOrderCreate(BaseModel):
    items: List[CustomerOrderItemCreate]
    pickup_address: Optional[str] = None
    delivery_address: Optional[str] = None
    pickup_date: Optional[datetime] = None
    special_instructions: Optional[str] = None
    is_express: bool = False
    coupon_code: Optional[str] = None

class OrderTimelineEntry(BaseModel):
    status: str
    timestamp: datetime
    description: str

class CustomerOrderItemOut(BaseModel):
    id: UUID
    service_id: UUID
    quantity: int
    price: Decimal

    class Config:
        from_attributes = True

class CustomerOrderOut(BaseModel):
    id: UUID
    order_number: Optional[str]
    status: Optional[str]
    total_amount: Decimal
    discount: Decimal
    paid_amount: Decimal
    payment_status: Optional[str]
    pickup_address: Optional[str]
    delivery_address: Optional[str]
    pickup_date: Optional[datetime]
    delivery_date: Optional[datetime]
    estimated_delivery_date: Optional[datetime]
    special_instructions: Optional[str]
    is_express: bool = False
    rating: Optional[int]
    review: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[CustomerOrderItemOut] = []

    class Config:
        from_attributes = True


# ── Payments ─────────────────────────────────────────────
class CustomerPaymentCreate(BaseModel):
    order_id: UUID
    amount: Decimal
    method: str = "CARD"  # CARD, UPI, WALLET, CASH

class CustomerPaymentOut(BaseModel):
    id: UUID
    order_id: UUID
    amount: Decimal
    method: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Wallet ───────────────────────────────────────────────
class WalletPayPayload(BaseModel):
    order_id: UUID
    amount: Decimal


# ── Loyalty ──────────────────────────────────────────────
class LoyaltyRedeemPayload(BaseModel):
    points: int


# ── Reviews ──────────────────────────────────────────────
class CustomerReviewCreate(BaseModel):
    rating: int  # 1-5
    comment: Optional[str] = None

class CustomerReviewOut(BaseModel):
    order_id: UUID
    order_number: Optional[str]
    rating: Optional[int]
    review: Optional[str]
    review_reply: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Support ──────────────────────────────────────────────
class CustomerTicketCreate(BaseModel):
    subject: str
    description: str
    priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH


# ── Addresses ────────────────────────────────────────────
class AddressCreate(BaseModel):
    label: str  # Home, Office, Apartment
    address_line: str
    is_default: bool = False

class AddressUpdate(BaseModel):
    label: Optional[str] = None
    address_line: Optional[str] = None
    is_default: Optional[bool] = None


# ── Dashboard ────────────────────────────────────────────
class DashboardOut(BaseModel):
    active_orders: int
    in_progress_orders: int
    ready_for_delivery: int
    delivered_orders: int
    pending_payments: int
    wallet_balance: Decimal
    loyalty_points: int
    unread_notifications: int
