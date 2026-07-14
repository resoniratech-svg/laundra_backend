from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from uuid import UUID
from typing import Optional

class CustomerSupportTicket(BaseModel):
    __tablename__ = "customer_support_tickets"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    subject: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="OPEN") # OPEN, IN_PROGRESS, RESPONDED, CLOSED
    priority: Mapped[str] = mapped_column(String(50), default="MEDIUM") # LOW, MEDIUM, HIGH
    admin_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
