from sqlalchemy import ForeignKey, String, Numeric, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime

class CashierShift(BaseModel):
    __tablename__ = "cashier_shifts"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    cashier_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    cashier_name: Mapped[str] = mapped_column(String(150), default="Cashier")
    
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    closing_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    expected_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    difference: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    
    cash_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    card_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    driver_handovers: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cash_expenses: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # 'OPEN', 'CLOSED'
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
