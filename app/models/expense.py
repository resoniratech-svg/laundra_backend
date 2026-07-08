from sqlalchemy import ForeignKey, String, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional
from decimal import Decimal

class Expense(BaseModel):
    __tablename__ = "expenses"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric)
    category: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="expenses")
