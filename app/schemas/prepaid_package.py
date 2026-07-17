from pydantic import BaseModel
from typing import Optional, List
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
    eligible_services: List[str]
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

class CustomerPackageResponse(CustomerPackageBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    purchase_date: datetime
    activation_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    total_quantity: int
    used_quantity: int
    status: str
    secure_token: str
    package: Optional[PrepaidPackageResponse] = None

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
