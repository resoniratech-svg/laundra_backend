from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
    
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=True) # Used if package is quantity-based
    used_quantity: Mapped[int] = mapped_column(Integer, default=0)
    
    package_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True, default=0.0) # For monetary packages
    current_balance: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True, default=0.0)
    used_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True, default=0.0)
    
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE") # ACTIVE, IN_USE, COMPLETED, EXPIRED, CANCELLED
    secure_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    apple_wallet_url: Mapped[str] = mapped_column(Text, nullable=True)

    pass_color: Mapped[str] = mapped_column(String(20), default="GOLD") # GOLD, GREY, ORANGE, WHITE

    # Dynamic JSONB column — single source of truth for ALL service types
    # Format: [{"service": "Wash & Press", "total": 10, "left": 10}, {"service": "Premium Services", "total": 5, "left": 5}, ...]
    service_items = mapped_column(JSONB, nullable=True, default=list)

    # Helper functions to get/set values from service_items JSON list
    def _get_service_val(self, key_contains: str, field: str) -> int:
        items = self.service_items or []
        for it in items:
            if isinstance(it, dict) and key_contains in it.get("service", "").lower():
                return it.get(field, 0)
        return 0

    def _set_service_val(self, key_contains: str, field: str, val: int):
        items = list(self.service_items or [])
        updated = False
        for it in items:
            if isinstance(it, dict) and key_contains in it.get("service", "").lower():
                it[field] = val
                updated = True
        if not updated:
            service_name = "Wash & Press" if "wash" in key_contains else ("Pressing" if "iron" in key_contains else ("Dry Cleaning" if "dry" in key_contains else "Steam Press"))
            items.append({"service": service_name, "total": val, "left": val})
        self.service_items = items

    @property
    def wash_total(self) -> int:
        return self._get_service_val("wash", "total")

    @wash_total.setter
    def wash_total(self, val: int):
        self._set_service_val("wash", "total", val)

    @property
    def wash_left(self) -> int:
        return self._get_service_val("wash", "left")

    @wash_left.setter
    def wash_left(self, val: int):
        self._set_service_val("wash", "left", val)

    @property
    def iron_total(self) -> int:
        return self._get_service_val("press", "total") or self._get_service_val("iron", "total")

    @iron_total.setter
    def iron_total(self, val: int):
        self._set_service_val("press", "total", val)

    @property
    def iron_left(self) -> int:
        return self._get_service_val("press", "left") or self._get_service_val("iron", "left")

    @iron_left.setter
    def iron_left(self, val: int):
        self._set_service_val("press", "left", val)

    @property
    def dry_total(self) -> int:
        return self._get_service_val("dry", "total")

    @dry_total.setter
    def dry_total(self, val: int):
        self._set_service_val("dry", "total", val)

    @property
    def dry_left(self) -> int:
        return self._get_service_val("dry", "left")

    @dry_left.setter
    def dry_left(self, val: int):
        self._set_service_val("dry", "left", val)

    @property
    def steam_total(self) -> int:
        return self._get_service_val("steam", "total")

    @steam_total.setter
    def steam_total(self, val: int):
        self._set_service_val("steam", "total", val)

    @property
    def steam_left(self) -> int:
        return self._get_service_val("steam", "left")

    @steam_left.setter
    def steam_left(self, val: int):
        self._set_service_val("steam", "left", val)

    company = relationship("Company")
    customer = relationship("User", foreign_keys=[customer_id])
    package = relationship("PrepaidPackage")
