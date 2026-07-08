from sqlalchemy import ForeignKey, String, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import List, Optional
from decimal import Decimal

class Service(BaseModel):
    __tablename__ = "services"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    unit: Mapped[Optional[str]] = mapped_column(String(20)) # KG / PIECE
    price: Mapped[Decimal] = mapped_column(Numeric)  # Normal price
    express_price: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)  # Express price (higher)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="services")
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="service")
