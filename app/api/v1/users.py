from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import uuid4, UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.repositories.user_repository import UserRepository
from app.core.security import get_password_hash

router = APIRouter()
user_repo = UserRepository()

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str # ACTIVE, INACTIVE

class PasswordReset(BaseModel):
    new_password: str

class EmailOTPRequest(BaseModel):
    email: str

@router.post("/send-otp")
def send_otp_for_user_creation(
    payload: EmailOTPRequest,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Admin sends OTP to a user (Cashier/Delivery) email before manual creation.
    """
    import random
    from app.api.v1.auth import MOCK_OTP_STORE
    from app.core.email_service import send_otp_email
    
    otp = str(random.randint(100000, 999999))
    MOCK_OTP_STORE[payload.email] = otp
    
    email_sent = send_otp_email(db, payload.email, otp)
    
    response = {"message": f"OTP sent successfully to {payload.email}"}
    if not email_sent:
        response["warning"] = "Platform SMTP not configured. Contact Super Admin."
        response["otp_debug"] = otp
    
    return response

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    from app.api.v1.auth import MOCK_OTP_STORE
    
    if not user_in.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required to verify OTP"
        )
        
    stored_otp = MOCK_OTP_STORE.get(user_in.email)
    if not stored_otp or stored_otp != user_in.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )
        
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    obj_data = user_in.model_dump()
    obj_data.pop("otp", None)
    obj_data["password"] = get_password_hash(obj_data["password"])
    obj_data["id"] = uuid4()
    obj_data["tenant_id"] = current_admin.tenant_id
    
    user = user_repo.create(db, obj_in=obj_data)
    MOCK_OTP_STORE.pop(user_in.email, None)
    return user

@router.get("", response_model=List[UserOut])
def list_users(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return user_repo.get_multi(db)

@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    user = user_repo.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    update_data = payload.model_dump(exclude_unset=True)
    return user_repo.update(db, db_obj=user, obj_in=update_data)

@router.patch("/{user_id}/status", response_model=UserOut)
def update_user_status(
    user_id: UUID,
    payload: StatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if payload.status not in ["ACTIVE", "INACTIVE"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be ACTIVE or INACTIVE"
        )
    user = user_repo.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    user.status = payload.status
    db.commit()
    db.refresh(user)
    return user

@router.patch("/{user_id}/reset-password")
def reset_user_password(
    user_id: UUID,
    payload: PasswordReset,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    user = user_repo.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    user.password = get_password_hash(payload.new_password)
    db.commit()
    return {"success": True, "message": "Password updated successfully"}

@router.get("/applications", response_model=List[UserOut])
def list_delivery_boy_applications(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = current_admin.tenant_id
    
    return db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "DELIVERY_BOY",
        User.status == "PENDING_APPROVAL"
    ).all()

@router.post("/{user_id}/approve", response_model=UserOut)
def approve_delivery_boy(
    user_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    from app.models.subscription import Subscription
    from app.core.email_service import send_otp_email
    from app.api.v1.auth import MOCK_OTP_STORE
    from app.models.audit_log import AuditLog
    import random
    
    tenant_id = current_admin.tenant_id
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id,
        User.role == "DELIVERY_BOY"
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery staff applicant not found"
        )
        
    # Check limit of delivery staff
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id,
        Subscription.status == "ACTIVE"
    ).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found for your company."
        )
        
    active_count = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "DELIVERY_BOY",
        User.status == "ACTIVE"
    ).count()
    
    if active_count >= sub.max_delivery_staff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve. Your company has reached its limit of {sub.max_delivery_staff} delivery staff. Please upgrade your subscription."
        )
        
    # Direct approval and activation
    from app.models.company import Company
    from app.core.email_service import send_approval_email
    
    company = db.query(Company).filter(Company.id == tenant_id).first()
    company_name = company.name if company else "our Laundry Platform"
    
    user.status = "ACTIVE"
    
    # Send email notification
    email_sent = send_approval_email(db, user.email, company_name)
    
    # Audit log
    audit_log = AuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_admin.id,
        action=f"Approved delivery boy application for {user.email}. Account is now ACTIVE.",
        module="STAFF_MANAGEMENT"
    )
    db.add(audit_log)
    db.commit()
    db.refresh(user)
    
    return user

@router.post("/{user_id}/reject", response_model=UserOut)
def reject_delivery_boy(
    user_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = current_admin.tenant_id
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant not found"
        )
        
    user.status = "REJECTED"
    db.commit()
    db.refresh(user)
    return user

