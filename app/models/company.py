from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import List, Optional

class Company(BaseModel):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[Optional[str]]
    email: Mapped[Optional[str]]
    password: Mapped[str]
    subdomain: Mapped[Optional[str]]
    logo: Mapped[Optional[str]]
    gst_number: Mapped[Optional[str]] = mapped_column(String(50))
    business_type: Mapped[Optional[str]] = mapped_column(String(100))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    street_name: Mapped[Optional[str]] = mapped_column(String(255))
    area: Mapped[Optional[str]] = mapped_column(String(255))
    shop_contact_no: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(default="ACTIVE")
    delivery_commission_percent: Mapped[Optional[float]] = mapped_column(default=0.0)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="company", cascade="all, delete-orphan")
    customers: Mapped[List["Customer"]] = relationship("Customer", back_populates="company", cascade="all, delete-orphan")
    services: Mapped[List["Service"]] = relationship("Service", back_populates="company", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="company", cascade="all, delete-orphan")
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="company", cascade="all, delete-orphan")
    coupons: Mapped[List["Coupon"]] = relationship("Coupon", back_populates="company", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="company", cascade="all, delete-orphan")
    deliveries: Mapped[List["Delivery"]] = relationship("Delivery", back_populates="company", cascade="all, delete-orphan")
