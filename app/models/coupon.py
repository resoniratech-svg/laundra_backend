from sqlalchemy import ForeignKey, String, Numeric, Date, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import date

class Coupon(BaseModel):
    __tablename__ = "coupons"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50))
    discount_type: Mapped[Optional[str]] = mapped_column(String(20))
    value: Mapped[Decimal] = mapped_column(Numeric)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    required_services: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="coupons")
