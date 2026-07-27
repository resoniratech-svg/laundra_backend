from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class BarcodeFormat(str, Enum):
    QR = "PKBarcodeFormatQR"
    PDF417 = "PKBarcodeFormatPDF417"
    CODE128 = "PKBarcodeFormatCode128"
    AZTEC = "PKBarcodeFormatAztec"

class PassField(BaseModel):
    key: str
    label: str
    value: Union[str, int, float]
    changeMessage: Optional[str] = None
    textAlignment: Optional[str] = None

class Barcode(BaseModel):
    format: BarcodeFormat = BarcodeFormat.QR
    message: str
    messageEncoding: str = "iso-8859-1"
    altText: Optional[str] = None

class Location(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    relevantText: Optional[str] = None

class PassStructure(BaseModel):
    headerFields: Optional[List[PassField]] = None
    primaryFields: Optional[List[PassField]] = None
    secondaryFields: Optional[List[PassField]] = None
    auxiliaryFields: Optional[List[PassField]] = None
    backFields: Optional[List[PassField]] = None

class WalletPassModel(BaseModel):
    formatVersion: int = 1
    passTypeIdentifier: str
    serialNumber: str
    teamIdentifier: str
    organizationName: str
    description: str
    logoText: Optional[str] = None
    foregroundColor: Optional[str] = "rgb(255, 255, 255)"
    backgroundColor: Optional[str] = "rgb(15, 23, 42)"
    labelColor: Optional[str] = "rgb(148, 163, 184)"
    barcodes: Optional[List[Barcode]] = None
    locations: Optional[List[Location]] = None
    
    storeCard: Optional[PassStructure] = None
    eventTicket: Optional[PassStructure] = None
    coupon: Optional[PassStructure] = None
    generic: Optional[PassStructure] = None
    boardingPass: Optional[PassStructure] = None

class LaundryPassData(BaseModel):
    company_name: Optional[str] = "Dry Cleaners"
    customer_name: str
    package_name: str
    package_id: str
    remaining_balance: str
    expiry_date: str
    qr_data: str
    status: Optional[str] = "ACTIVE"
    member_since: Optional[str] = "2026"
    coupon_cost: Optional[str] = "QR 0.00"
    # Dynamic service items — works with ANY service type
    service_items: Optional[List[dict]] = []  # [{"service": "Wash & Press", "total": 10, "left": 8}, ...]
    # Legacy fixed fields (backward compat, defaults to 0 instead of hardcoded values)
    wash_left: Optional[int] = 0
    wash_total: Optional[int] = 0
    iron_left: Optional[int] = 0
    iron_total: Optional[int] = 0
    dry_left: Optional[int] = 0
    dry_total: Optional[int] = 0
    steam_left: Optional[int] = 0
    steam_total: Optional[int] = 0

class PassGenerationRequest(BaseModel):
    customer_id: UUID
    order_id: Optional[UUID] = None
    package_id: Optional[UUID] = None
    customer_name: str
    package_name: str
    remaining_balance: str
    expiry_date: Optional[str] = None

class PassGenerationResponse(BaseModel):
    success: bool
    serial_number: str
    pass_id: Optional[UUID] = None
    download_url: str
    file_path: Optional[str] = None
