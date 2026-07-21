from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional
import enum

class WalletPassStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class WalletPass(BaseModel):
    __tablename__ = "wallet_passes"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)

    pass_type_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    authentication_token: Mapped[str] = mapped_column(String(255), nullable=False)
    qr_token: Mapped[str] = mapped_column(String(500), nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    pass_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company")
    customer: Mapped["Customer"] = relationship("Customer")
