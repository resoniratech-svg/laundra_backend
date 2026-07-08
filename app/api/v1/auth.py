from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from uuid import UUID, uuid4
from typing import Optional
from decimal import Decimal

from app.core.database import get_db
from app.services.auth_service import AuthService
from app.schemas.user import CompanyRegisterRequest, LoginRequest, TokenResponse, UserOut
from app.dependencies import get_current_user
from app.models.user import User
from app.models.company import Company
from app.core.security import get_password_hash

router = APIRouter()

class DeliveryBoyRegisterRequest(BaseModel):
    company_code: UUID # the tenant_id
    name: str
    phone: str
    email: EmailStr
    password: str
    otp: str
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

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: CompanyRegisterRequest,
    db: Session = Depends(get_db)
):
    company, admin_user = AuthService.register_company(
        db,
        company_name=payload.company_name,
        email=payload.email,
        phone=payload.phone,
        password=payload.password
    )
    return {
        "message": "Company and Admin registered successfully",
        "company_id": company.id,
        "admin_id": admin_user.id
    }

class DeliveryBoySendOTPRequest(BaseModel):
    email: EmailStr

@router.post("/delivery-boy/send-otp")
def delivery_boy_send_otp(
    payload: DeliveryBoySendOTPRequest,
    db: Session = Depends(get_db)
):
    import random
    from app.core.email_service import send_otp_email
    
    otp = str(random.randint(100000, 999999))
    MOCK_OTP_STORE[payload.email] = otp
    
    email_sent = send_otp_email(db, payload.email, otp)
    response = {"message": f"OTP sent successfully to {payload.email}"}
    if not email_sent:
        response["warning"] = "Platform SMTP not configured. Contact Super Admin."
        response["otp_debug"] = otp
    return response

@router.post("/delivery-boy/register", status_code=status.HTTP_201_CREATED)
def register_delivery_boy(
    payload: DeliveryBoyRegisterRequest,
    db: Session = Depends(get_db)
):
    stored_otp = MOCK_OTP_STORE.get(payload.email)
    if not stored_otp or stored_otp != payload.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )

    company = db.query(Company).filter(Company.id == payload.company_code).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found with the provided Company Code"
        )
        
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    user = User(
        id=uuid4(),
        tenant_id=payload.company_code,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        password=get_password_hash(payload.password),
        role="DELIVERY_BOY",
        status="PENDING_APPROVAL",
        profile_photo=payload.profile_photo,
        vehicle_type=payload.vehicle_type,
        vehicle_number=payload.vehicle_number,
        license_number=payload.license_number,
        address=payload.address,
        vehicle_rc=payload.vehicle_rc,
        insurance_number=payload.insurance_number,
        emergency_contact=payload.emergency_contact,
        license_file=payload.license_file,
        insurance_file=payload.insurance_file
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    MOCK_OTP_STORE.pop(payload.email, None)
    return {
        "message": "Application submitted successfully. Waiting for company approval.",
        "user_id": user.id
    }

@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):
    token_data = AuthService.login(db, email=payload.email, password=payload.password)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
    return token_data

@router.get("/me", response_model=UserOut)
def me(
    current_user: User = Depends(get_current_user)
):
    return current_user

# Simple in-memory dict to store OTP codes
MOCK_OTP_STORE = {}

class OTPSendRequest(BaseModel):
    email: EmailStr
    company_code: UUID  # the tenant_id (to verify company exists)

class CustomerRegisterRequest(BaseModel):
    company_code: UUID # the tenant_id
    name: str
    phone: str
    email: EmailStr
    password: str
    otp: str
    address: Optional[str] = None

@router.post("/customer/send-otp")
def send_customer_otp(
    payload: OTPSendRequest,
    db: Session = Depends(get_db)
):
    import random
    from app.core.email_service import send_otp_email
    
    # Verify company exists
    company = db.query(Company).filter(Company.id == payload.company_code).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found with the provided Company Code"
        )
    
    otp = str(random.randint(100000, 999999))
    MOCK_OTP_STORE[payload.email] = otp
    
    # Send real email using Super Admin's platform SMTP settings
    email_sent = send_otp_email(db, payload.email, otp)
    
    response = {"message": "OTP sent successfully to email"}
    if not email_sent:
        response["warning"] = "Platform SMTP not configured. Contact Super Admin."
        response["otp_debug"] = otp  # Fallback: show OTP in response only when email fails
    
    return response

@router.post("/customer/register", status_code=status.HTTP_201_CREATED)
def register_customer(
    payload: CustomerRegisterRequest,
    db: Session = Depends(get_db)
):
    stored_otp = MOCK_OTP_STORE.get(payload.email)
    if not stored_otp or stored_otp != payload.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )
        
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    company = db.query(Company).filter(Company.id == payload.company_code).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found with the provided Company Code"
        )
        
    user_id = uuid4()
    qr_secret = uuid4().hex
    
    new_user = User(
        id=user_id,
        tenant_id=payload.company_code,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        password=get_password_hash(payload.password),
        role="CUSTOMER",
        status="ACTIVE"
    )
    
    from app.models.customer import Customer
    new_customer = Customer(
        id=user_id,
        tenant_id=payload.company_code,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        address=payload.address or "",
        wallet_balance=Decimal("0.0"),
        loyalty_points=0,
        qr_secret=qr_secret,
        qr_status="ACTIVE"
    )
    
    db.add(new_user)
    db.add(new_customer)
    db.commit()
    db.refresh(new_user)
    
    MOCK_OTP_STORE.pop(payload.email, None)
    
    from app.core.security import create_access_token
    token = create_access_token(
        subject=f"{user_id}:{qr_secret}", 
        role="CUSTOMER", 
        tenant_id=str(payload.company_code)
    )
    portal_url = f"https://portal.laundry.com/login?token={token}"
    
    return {
        "message": "Customer registered successfully",
        "customer_id": new_user.id,
        "portal_url": portal_url
    }

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    import random
    from app.core.email_service import send_otp_email
    
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user registered with this email"
        )
        
    otp = str(random.randint(100000, 999999))
    MOCK_OTP_STORE[payload.email] = otp
    
    email_sent = send_otp_email(db, payload.email, otp)
    
    response = {"message": "OTP for password reset sent successfully to email"}
    if not email_sent:
        response["warning"] = "Platform SMTP not configured. Contact Super Admin."
        response["otp_debug"] = otp
        
    return response

@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    stored_otp = MOCK_OTP_STORE.get(payload.email)
    if not stored_otp or stored_otp != payload.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )
        
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    user.password = get_password_hash(payload.new_password)
    db.commit()
    
    MOCK_OTP_STORE.pop(payload.email, None)
    return {"success": True, "message": "Password reset successfully"}

# End of auth routes


