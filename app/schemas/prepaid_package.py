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
    package: Optional[PrepaidPackageResponse] = None
    wallet_generation: Optional[WalletGenerationStatus] = None

    class Config:
        from_attributes = True
        
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
