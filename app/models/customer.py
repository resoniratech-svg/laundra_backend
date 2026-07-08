from sqlalchemy import ForeignKey, String, Text, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import List, Optional
from decimal import Decimal

class Customer(BaseModel):
    __tablename__ = "customers"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(Text)
    wallet_balance: Mapped[Decimal] = mapped_column(Numeric, default=0.0)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    
    referral_code: Mapped[Optional[str]] = mapped_column(String(50))
    referred_by_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    
    qr_secret: Mapped[Optional[str]] = mapped_column(String(255))
    qr_status: Mapped[str] = mapped_column(String(50), default="NOT_SHARED_YET")
    profile_photo: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="customers")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    addresses: Mapped[List["CustomerAddress"]] = relationship("CustomerAddress", cascade="all, delete-orphan")
