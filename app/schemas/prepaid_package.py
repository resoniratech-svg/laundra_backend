from pydantic import BaseModel
from typing import Optional, List, Any
from decimal import Decimal
from datetime import date, datetime
import uuid

class PrepaidPackageBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    original_price: Decimal
    offer_price: Decimal
    total_quantity: int
    eligible_services: List[Any]
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
    used_quantity: int
    package_value: float
    current_balance: float
    used_amount: float
    status: str
    secure_token: str
    apple_wallet_url: Optional[str] = None
    google_wallet_url: Optional[str] = None
    pass_color: str
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
