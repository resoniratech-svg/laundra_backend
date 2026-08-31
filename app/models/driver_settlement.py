from sqlalchemy import ForeignKey, String, DateTime, Numeric, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional, Any
from decimal import Decimal
from datetime import datetime

class DriverSettlement(BaseModel):
    __tablename__ = "driver_settlements"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    settlement_number: Mapped[Optional[str]] = mapped_column(String(100))
    driver_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    driver_name: Mapped[Optional[str]] = mapped_column(String(255))
    settled_by: Mapped[Optional[str]] = mapped_column(String(255))
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    cash_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0)
    card_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0)
    cheque_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    orders: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="SETTLED")

    # Relationships
    company: Mapped["Company"] = relationship("Company")
    driver: Mapped[Optional["User"]] = relationship("User")
