from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional
from decimal import Decimal

class OrderItem(BaseModel):
    __tablename__ = "order_items"

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[Decimal] = mapped_column(Numeric, default=0.0)

    # Item-Level Quantity & Status Tracking
    ordered_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    picked_up_quantity: Mapped[int] = mapped_column(Integer, default=0)
    pickup_pending_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivered_quantity: Mapped[int] = mapped_column(Integer, default=0)
    delivery_pending_quantity: Mapped[int] = mapped_column(Integer, default=0)
    item_status: Mapped[Optional[str]] = mapped_column(String(30), default="CREATED")

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    service: Mapped["Service"] = relationship("Service", back_populates="order_items")
