from sqlalchemy import String, Integer, Float, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from typing import Optional

class SubscriptionPlan(BaseModel):
    __tablename__ = "subscription_plans"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    billing_cycle: Mapped[str] = mapped_column(String(50), default="MONTHLY") # MONTHLY, YEARLY
    
    # Granular Resource Limits
    max_admins: Mapped[int] = mapped_column(Integer, default=1)
    max_cashiers: Mapped[int] = mapped_column(Integer, default=0)
    max_delivery_staff: Mapped[int] = mapped_column(Integer, default=0)
    max_customers: Mapped[int] = mapped_column(Integer, default=100)
    max_orders_per_month: Mapped[int] = mapped_column(Integer, default=100)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=1024) # 1GB
    max_api_requests: Mapped[int] = mapped_column(Integer, default=1000)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
