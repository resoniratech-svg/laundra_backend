import datetime
from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import Optional

class AppleDeviceRegistration(BaseModel):
    __tablename__ = "apple_device_registrations"

    device_library_identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    push_token: Mapped[str] = mapped_column(String(255), nullable=False)
    pass_type_identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    serial_number: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    wallet_pass_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("wallet_passes.id", ondelete="CASCADE"), nullable=True, index=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    wallet_pass = relationship("WalletPass", foreign_keys=[wallet_pass_id])
