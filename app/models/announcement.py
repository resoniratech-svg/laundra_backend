from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from datetime import datetime
from typing import Optional

class Announcement(BaseModel):
    __tablename__ = "announcements"

    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="PUBLISHED") # PUBLISHED, SCHEDULED, ARCHIVED
    tenant_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("companies.id")) # Null means Super Admin
    target_audience: Mapped[str] = mapped_column(String(50), default="ALL") # ALL, ADMINS, CUSTOMERS, DELIVERY_BOYS
    target_companies: Mapped[Optional[str]] = mapped_column(Text) # comma-separated company UUIDs or null for all
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
