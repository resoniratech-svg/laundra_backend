from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    role: str  # ADMIN | DELIVERY_BOY | CUSTOMER
    profile_photo: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    license_number: Optional[str] = None
    address: Optional[str] = None
    vehicle_rc: Optional[str] = None
    insurance_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    license_file: Optional[str] = None
    insurance_file: Optional[str] = None

class UserCreate(UserBase):
    password: str
    otp: str

class UserOut(UserBase):
    id: UUID
    tenant_id: Optional[UUID] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class CompanyRegisterRequest(BaseModel):
    company_name: str
    email: EmailStr
    phone: str
    password: str

from typing import Optional
from uuid import UUID

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: Optional[UUID] = None
    role: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
