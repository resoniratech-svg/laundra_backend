from sqlalchemy import ForeignKey, String, DateTime, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime

class Delivery(BaseModel):
    __tablename__ = "deliveries"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    delivery_boy_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"))
    type: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[Optional[str]] = mapped_column(String(20))
    otp: Mapped[Optional[str]] = mapped_column(String(10))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    photos: Mapped[Optional[str]] = mapped_column(String(2000))
    notes: Mapped[Optional[str]] = mapped_column(String(1000))
    pickup_commission: Mapped[Optional[Decimal]] = mapped_column(Numeric, default=0.0, nullable=True)
    delivery_commission: Mapped[Optional[Decimal]] = mapped_column(Numeric, default=0.0, nullable=True)
    pickup_commission_paid: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    delivery_commission_paid: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    pickup_payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    delivery_payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="deliveries")
    order: Mapped["Order"] = relationship("Order", back_populates="deliveries")
    delivery_boy: Mapped[Optional["User"]] = relationship("User", back_populates="deliveries")
