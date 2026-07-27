from pydantic import BaseModel
from typing import Optional, List, Any
from decimal import Decimal
from datetime import date, datetime
import uuid

class PrepaidPackageBase(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    original_price: Optional[Decimal] = Decimal('0.0')
    offer_price: Optional[Decimal] = Decimal('0.0')
    total_quantity: Optional[int] = 0
    eligible_services: Optional[List[Any]] = []
    validity_days: Optional[int] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_active: Optional[bool] = True

class PrepaidPackageCreate(PrepaidPackageBase):
    pass

class PrepaidPackageResponse(PrepaidPackageBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    
    class Config:
        from_attributes = True

class CustomerPackageBase(BaseModel):
    package_id: uuid.UUID
    
class CustomerPackageCreate(CustomerPackageBase):
    customer_id: uuid.UUID
    coupon_code: Optional[str] = None

class WalletGenerationStatus(BaseModel):
    google_wallet: bool = False
    apple_wallet: bool = False
    qr_code: bool = False

class CustomerPackageResponse(CustomerPackageBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    purchase_date: datetime
    activation_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    total_quantity: Optional[int] = None
    used_quantity: Optional[int] = 0
    package_value: Optional[float] = 0.0
    current_balance: Optional[float] = 0.0
    used_amount: Optional[float] = 0.0
    status: Optional[str] = "ACTIVE"
    secure_token: Optional[str] = None
    apple_wallet_url: Optional[str] = None
    google_wallet_url: Optional[str] = None
    pass_color: Optional[str] = "GOLD"
    wash_total: Optional[int] = 0
    wash_left: Optional[int] = 0
    iron_total: Optional[int] = 0
    iron_left: Optional[int] = 0
    dry_total: Optional[int] = 0
    dry_left: Optional[int] = 0
    steam_total: Optional[int] = 0
    steam_left: Optional[int] = 0
    service_items: Optional[List[Any]] = []  # Dynamic: [{"service": "Wash & Press", "total": 10, "left": 8}, ...]
    package: Optional[PrepaidPackageResponse] = None
    wallet_generation: Optional[WalletGenerationStatus] = None

    class Config:
        from_attributes = True

class ServiceDeduction(BaseModel):
    service: str           # Exact service name, e.g. "Wash & Press", "Premium Services"
    quantity: int = 0      # How many to deduct

class CustomerPackageDeductRequest(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    customer_package_id: Optional[uuid.UUID] = None
    # Dynamic service deductions — works with ANY service name
    deductions: Optional[List[ServiceDeduction]] = []
    # Legacy fixed-field deductions (still supported for backward compat)
    wash_used: Optional[int] = 0
    iron_used: Optional[int] = 0
    dry_used: Optional[int] = 0
    steam_used: Optional[int] = 0
    amount_used: Optional[float] = 0.0
    remarks: Optional[str] = None
        
class PackageRedeemRequest(BaseModel):
    secure_token: str
    order_id: uuid.UUID
    quantity_used: int

class PackageUsageHistoryResponse(BaseModel):
    id: uuid.UUID
    customer_package_id: uuid.UUID
    order_id: uuid.UUID
    quantity_used: int
    transaction_date: datetime

    class Config:
        from_attributes = True
