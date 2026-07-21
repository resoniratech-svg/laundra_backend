from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime

from app.models.base import Base
from app.core.config import settings

class WalletPass(Base):
    __tablename__ = "wallet_passes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    customer_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_packages.id"), nullable=False)
    
    class_id: Mapped[str] = mapped_column(String(150), nullable=True, default=lambda: settings.GOOGLE_WALLET_CLASS_ID)
    wallet_object_id: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    wallet_url: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    @property
    def object_id(self):
        return self.wallet_object_id

    @object_id.setter
    def object_id(self, value):
        self.wallet_object_id = value

    @property
    def pass_status(self):
        return self.status

    @pass_status.setter
    def pass_status(self, value):
        self.status = value

    company = relationship("Company")
    customer = relationship("User", foreign_keys=[customer_id])
    customer_package = relationship("CustomerPackage")
