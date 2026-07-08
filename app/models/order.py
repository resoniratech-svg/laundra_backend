from sqlalchemy import ForeignKey, String, Numeric, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

class Order(BaseModel):
    __tablename__ = "orders"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    order_number: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(30))
    total_amount: Mapped[Decimal] = mapped_column(Numeric, default=0.0)
    discount: Mapped[Decimal] = mapped_column(Numeric, default=0.0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric, default=0.0)
    payment_status: Mapped[Optional[str]] = mapped_column(String(20))
    qr_code: Mapped[Optional[str]] = mapped_column(Text)
    pickup_address: Mapped[Optional[str]] = mapped_column(Text)
    delivery_address: Mapped[Optional[str]] = mapped_column(Text)
    pickup_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    delivery_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    estimated_delivery_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text)
    is_express: Mapped[bool] = mapped_column(Boolean, default=False)
    
    rating: Mapped[Optional[int]]
    review: Mapped[Optional[str]] = mapped_column(String(1000))
    review_reply: Mapped[Optional[str]] = mapped_column(String(1000))
    review_hidden: Mapped[bool] = mapped_column(default=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="orders")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    deliveries: Mapped[List["Delivery"]] = relationship("Delivery", back_populates="order", cascade="all, delete-orphan")
