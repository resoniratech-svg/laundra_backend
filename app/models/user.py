from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from typing import List, Optional

class User(BaseModel):
    __tablename__ = "users"

    tenant_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("companies.id"),
        nullable=True
    )
    name: Mapped[Optional[str]]
    phone: Mapped[Optional[str]]
    email: Mapped[Optional[str]]
    password: Mapped[Optional[str]]
    role: Mapped[Optional[str]]
    status: Mapped[str] = mapped_column(default="ACTIVE")
    
    profile_photo: Mapped[Optional[str]] = mapped_column(String(500))
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(100))
    vehicle_number: Mapped[Optional[str]] = mapped_column(String(100))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    vehicle_rc: Mapped[Optional[str]] = mapped_column(String(500))
    insurance_number: Mapped[Optional[str]] = mapped_column(String(100))
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(100))
    license_file: Mapped[Optional[str]] = mapped_column(String(500))
    insurance_file: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="users")
    deliveries: Mapped[List["Delivery"]] = relationship("Delivery", back_populates="delivery_boy")
    notifications: Mapped[List["Notification"]] = relationship("Notification", cascade="all, delete-orphan")
    support_tickets: Mapped[List["SupportTicket"]] = relationship("SupportTicket", cascade="all, delete-orphan")
