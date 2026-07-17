from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime

from app.models.base import Base

class CustomerPackage(Base):
    __tablename__ = "customer_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prepaid_packages.id"), nullable=False)
    
    purchase_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    activation_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    used_quantity: Mapped[int] = mapped_column(Integer, default=0)
    
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE") # ACTIVE, EXPIRED, FULLY_UTILIZED, CANCELLED
    secure_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    company = relationship("Company")
    customer = relationship("User", foreign_keys=[customer_id])
    package = relationship("PrepaidPackage")
