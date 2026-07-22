import enum
import datetime
from sqlalchemy import ForeignKey, String, Text, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional
class WalletPassStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class WalletPass(BaseModel):
    __tablename__ = "wallet_passes"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_package_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("customer_packages.id", ondelete="SET NULL"), nullable=True, index=True)

    # Apple Wallet Fields
    pass_type_identifier: Mapped[str] = mapped_column(String(255), nullable=True) # Renamed conceptually or repurposed to apple_pass_type_identifier if we want, but keeping existing column names where possible.
    serial_number: Mapped[str] = mapped_column(String(255), unique=True, nullable=True, index=True)
    authentication_token: Mapped[str] = mapped_column(String(255), nullable=True)
    qr_token: Mapped[str] = mapped_column(String(500), nullable=True)
    pass_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    apple_serial_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    apple_pass_type_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    apple_pass_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)



    # QR Code Field
    qr_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Shared Wallet Metadata
    wallet_status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE") # Keeping existing status column
    original_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    remaining_balance: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    expiry_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    wallet_created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    wallet_updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


    # Relationships
    company: Mapped["Company"] = relationship("Company")
    customer: Mapped["User"] = relationship("User", foreign_keys=[customer_id])
    customer_package = relationship("CustomerPackage")
