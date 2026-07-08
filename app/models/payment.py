from sqlalchemy import ForeignKey, String, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional
from decimal import Decimal

class Payment(BaseModel):
    __tablename__ = "payments"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric)
    method: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(default="SUCCESS")
    delivery_boy_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    delivery_boy_commission: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="payments")
    order: Mapped["Order"] = relationship("Order", back_populates="payments")
