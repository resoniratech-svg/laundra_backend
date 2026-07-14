from typing import Optional
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from uuid import UUID

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"

    tenant_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(255))
    module: Mapped[str] = mapped_column(String(100))
