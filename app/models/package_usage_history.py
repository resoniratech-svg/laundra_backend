from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime

from app.models.base import Base

class PackageUsageHistory(Base):
    __tablename__ = "package_usage_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    customer_package_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_packages.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    
    quantity_used: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    company = relationship("Company")
    customer_package = relationship("CustomerPackage")
    order = relationship("Order")
