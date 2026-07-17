from sqlalchemy import Column, String, Text, Numeric, Integer, Date, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base

class PrepaidPackage(Base):
    __tablename__ = "prepaid_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    original_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    offer_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_services: Mapped[list] = mapped_column(JSON, nullable=False) # List of service IDs
    
    validity_days: Mapped[int] = mapped_column(Integer, nullable=True)
    start_date: Mapped[str] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[str] = mapped_column(Date, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    company = relationship("Company")
