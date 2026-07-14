from sqlalchemy import String, ForeignKey, Integer, Date, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from uuid import UUID
from datetime import date
from typing import Optional

class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True)
    plan_name: Mapped[str] = mapped_column(String(50), default="FREE_TRIAL") # FREE_TRIAL, STARTER, PROFESSIONAL, ENTERPRISE
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE") # ACTIVE, EXPIRED, SUSPENDED, CANCELLED
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    max_admins: Mapped[int] = mapped_column(Integer, default=1)
    max_cashiers: Mapped[int] = mapped_column(Integer, default=0)
    max_delivery_staff: Mapped[int] = mapped_column(Integer, default=0)
    max_customers: Mapped[int] = mapped_column(Integer, default=100)
    max_orders_per_month: Mapped[int] = mapped_column(Integer, default=100)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=1024)
    max_api_requests: Mapped[int] = mapped_column(Integer, default=1000)
    end_date: Mapped[date] = mapped_column(Date)
    
    trial_start_date: Mapped[Optional[date]] = mapped_column(Date)
    trial_end_date: Mapped[Optional[date]] = mapped_column(Date)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="subscription")
