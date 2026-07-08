from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.company import Company

router = APIRouter()

def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SaaS super administrators can access this resource"
        )
    return current_user

class CompanyCreatePayload(BaseModel):
    name: str
    email: EmailStr
    phone: str
    address: Optional[str] = None
    street_name: Optional[str] = None
    area: Optional[str] = None
    shop_contact_no: Optional[str] = None
    gst_number: Optional[str] = None
    business_type: Optional[str] = None
    logo: Optional[str] = None

class CompanyUpdatePayload(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    street_name: Optional[str] = None
    area: Optional[str] = None
    shop_contact_no: Optional[str] = None
    gst_number: Optional[str] = None
    business_type: Optional[str] = None
    logo: Optional[str] = None
    status: Optional[str] = None

class AdminCreatePayload(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str
    otp: str

class AdminSendOTPPayload(BaseModel):
    email: EmailStr

@router.get("/companies")
def list_all_companies(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    return db.query(Company).filter(Company.status != "DELETED").all()

@router.post("/companies", status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreatePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from uuid import uuid4
    from app.core.security import get_password_hash
    # We create a dummy password for the company record itself since it's required by the model
    # Real login happens via Users table
    new_company = Company(
        id=uuid4(),
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password=get_password_hash("dummy123"),
        address=payload.address,
        street_name=payload.street_name,
        area=payload.area,
        shop_contact_no=payload.shop_contact_no,
        gst_number=payload.gst_number,
        business_type=payload.business_type,
        logo=payload.logo,
        status="ACTIVE"
    )
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    return new_company

@router.get("/companies/{id}")
def get_company_details(
    id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.id == id, Company.status != "DELETED").first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.put("/companies/{id}")
def update_company(
    id: UUID,
    payload: CompanyUpdatePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.id == id, Company.status != "DELETED").first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
        
    db.commit()
    db.refresh(company)
    return company

@router.delete("/companies/{id}")
def soft_delete_company(
    id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.id == id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.status = "DELETED"
    db.commit()
    return {"message": "Company deleted successfully"}

@router.post("/companies/{id}/status")
def update_company_status(
    id: UUID,
    status: str, # ACTIVE, SUSPENDED
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    if status not in ["ACTIVE", "SUSPENDED"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be ACTIVE or SUSPENDED"
        )
        
    company = db.query(Company).filter(Company.id == id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    company.status = status
    db.commit()
    db.refresh(company)
    return company

@router.post("/companies/{company_id}/admins/send-otp")
def send_admin_otp(
    company_id: UUID,
    payload: AdminSendOTPPayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    import random
    from app.core.email_service import send_otp_email
    from app.api.v1.auth import MOCK_OTP_STORE
    
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    otp = str(random.randint(100000, 999999))
    MOCK_OTP_STORE[payload.email] = otp
    send_otp_email(db, payload.email, otp)
    
    return {"message": "OTP sent successfully to email", "otp_debug": otp}

@router.post("/companies/{company_id}/admins", status_code=status.HTTP_201_CREATED)
def create_company_admin(
    company_id: UUID,
    payload: AdminCreatePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """
    Creates a new Company Admin. This generates a random OTP and sends it
    using the platform's centralized email service.
    The admin will need this OTP to verify their account or login for the first time.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check resource limits
    from app.models.subscription import Subscription
    sub = db.query(Subscription).filter(Subscription.tenant_id == company_id).first()
    if not sub:
        raise HTTPException(status_code=400, detail="Company must have a subscription plan first")

    from app.models.user import User
    from sqlalchemy import func
    current_admins = db.query(func.count(User.id)).filter(
        User.tenant_id == company_id, User.role == "ADMIN"
    ).scalar() or 0

    if current_admins >= sub.max_admins:
        raise HTTPException(
            status_code=400, 
            detail=f"Resource limit reached: Maximum {sub.max_admins} admins allowed."
        )

    from uuid import uuid4
    from app.core.security import get_password_hash
    from app.api.v1.auth import MOCK_OTP_STORE

    stored_otp = MOCK_OTP_STORE.get(payload.email)
    if not stored_otp or stored_otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    hashed_password = get_password_hash(payload.password)

    new_admin = User(
        id=uuid4(),
        tenant_id=company_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password=hashed_password,
        role="ADMIN",
        status="ACTIVE"
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    MOCK_OTP_STORE.pop(payload.email, None)

    return {
        "message": "Company Admin verified and created successfully.",
        "admin": new_admin
    }

@router.get("/companies/{company_id}/admins")
def list_company_admins(
    company_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.user import User
    return db.query(User).filter(User.tenant_id == company_id, User.role == "ADMIN").all()

@router.put("/admins/{admin_id}/status")
def change_admin_status(
    admin_id: UUID,
    status: str, # ACTIVE, SUSPENDED
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.user import User
    admin = db.query(User).filter(User.id == admin_id, User.role == "ADMIN").first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
        
    if status not in ["ACTIVE", "SUSPENDED"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    admin.status = status
    db.commit()
    db.refresh(admin)
    return admin


@router.get("/metrics")
def get_platform_metrics(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.company import Company
    from app.models.subscription import Subscription
    from app.models.order import Order
    from app.models.user import User
    from app.models.customer import Customer
    from app.models.audit_log import AuditLog
    from sqlalchemy import func

    # Companies
    total_companies = db.query(func.count(Company.id)).scalar() or 0
    active_companies = db.query(func.count(Company.id)).filter(Company.status == "ACTIVE").scalar() or 0
    suspended_companies = db.query(func.count(Company.id)).filter(Company.status == "SUSPENDED").scalar() or 0
    
    # Subscriptions
    free_trial_companies = db.query(func.count(Subscription.id)).filter(Subscription.plan_name == "FREE_TRIAL").scalar() or 0
    expired_subscriptions = db.query(func.count(Subscription.id)).filter(Subscription.status == "EXPIRED").scalar() or 0

    # Users across all companies
    total_admins = db.query(func.count(User.id)).filter(User.role == "ADMIN").scalar() or 0
    total_cashiers = db.query(func.count(User.id)).filter(User.role == "CASHIER").scalar() or 0
    total_delivery = db.query(func.count(User.id)).filter(User.role == "DELIVERY_BOY").scalar() or 0
    total_customers = db.query(func.count(Customer.id)).scalar() or 0

    # Orders & Revenue
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    
    # Calculate MRR based on active non-trial subscriptions (Approximation for now)
    active_subs = db.query(Subscription.plan_name, func.count(Subscription.id)).filter(Subscription.status == "ACTIVE").group_by(Subscription.plan_name).all()
    mrr = 0.0
    for plan, count in active_subs:
        # We should ideally fetch prices from SubscriptionPlan, but using defaults if not joined
        if plan == "STARTER": mrr += count * 49.0
        elif plan == "PROFESSIONAL": mrr += count * 99.0
        elif plan == "ENTERPRISE": mrr += count * 299.0

    # Recent Data
    recent_registrations = db.query(Company.name, Company.created_at).order_by(Company.created_at.desc()).limit(5).all()
    recent_activities = db.query(AuditLog.action, AuditLog.created_at).order_by(AuditLog.created_at.desc()).limit(10).all()

    return {
        "companies": {
            "total": total_companies,
            "active": active_companies,
            "suspended": suspended_companies,
            "on_free_trial": free_trial_companies,
            "expired_subscriptions": expired_subscriptions
        },
        "users": {
            "admins": total_admins,
            "cashiers": total_cashiers,
            "delivery_staff": total_delivery,
            "customers": total_customers
        },
        "platform": {
            "total_orders": total_orders,
            "monthly_recurring_revenue": mrr
        },
        "recent_registrations": [{"name": c.name, "date": c.created_at} for c in recent_registrations],
        "recent_activities": [{"action": a.action, "date": a.created_at} for a in recent_activities]
    }

class FeatureEnablePayload(BaseModel):
    feature_key: str

class FeatureTogglePayload(BaseModel):
    is_enabled: bool

@router.post("/companies/{company_id}/features")
def enable_company_feature(
    company_id: UUID,
    payload: FeatureEnablePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.company_feature import CompanyFeature
    from uuid import uuid4
    
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
        
    feat_key = payload.feature_key.upper()
    existing = db.query(CompanyFeature).filter(
        CompanyFeature.tenant_id == company_id,
        CompanyFeature.feature_key == feat_key
    ).first()
    if existing:
        existing.is_enabled = True
        db.commit()
        db.refresh(existing)
        return existing
        
    feat = CompanyFeature(
        id=uuid4(),
        tenant_id=company_id,
        feature_key=feat_key,
        is_enabled=True
    )
    db.add(feat)
    db.commit()
    db.refresh(feat)
    return feat

@router.patch("/companies/{company_id}/features/{feature_key}")
def toggle_company_feature(
    company_id: UUID,
    feature_key: str,
    payload: FeatureTogglePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.company_feature import CompanyFeature
    feat = db.query(CompanyFeature).filter(
        CompanyFeature.tenant_id == company_id,
        CompanyFeature.feature_key == feature_key.upper()
    ).first()
    if not feat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature configuration not found for this company"
        )
        
    feat.is_enabled = payload.is_enabled
    db.commit()
    db.refresh(feat)
    return feat

@router.get("/companies/{company_id}/features")
def list_company_features(
    company_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.company_feature import CompanyFeature
    return db.query(CompanyFeature).filter(CompanyFeature.tenant_id == company_id).all()

class SubscriptionAssignPayload(BaseModel):
    plan_name: str
    days: int = 14

class SubscriptionExtendPayload(BaseModel):
    days: int

class SubscriptionStatusPayload(BaseModel):
    status: str

@router.post("/subscriptions/{tenant_id}/assign")
def assign_tenant_subscription(
    tenant_id: UUID,
    payload: SubscriptionAssignPayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.subscription import Subscription
    from app.models.subscription_plan import SubscriptionPlan
    from uuid import uuid4
    from datetime import date, timedelta
    
    plan_name = payload.plan_name.upper()
    plan_model = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan_name).first()
    
    if not plan_model and plan_name == "FREE_TRIAL":
        class MockPlan:
            max_admins = 1
            max_cashiers = 2
            max_delivery_staff = 2
            max_customers = 100
            max_orders_per_month = 500
            max_storage_mb = 500
            max_api_requests = 500
        plan_model = MockPlan()
    elif not plan_model:
        raise HTTPException(status_code=400, detail=f"Subscription plan '{plan_name}' does not exist.")
    
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if not sub:
        sub = Subscription(
            id=uuid4(),
            tenant_id=tenant_id
        )
        db.add(sub)
        
    sub.plan_name = plan_name
    sub.status = "ACTIVE"
    sub.end_date = date.today() + timedelta(days=payload.days)
    
    # Copy limits from plan
    sub.max_admins = plan_model.max_admins
    sub.max_cashiers = plan_model.max_cashiers
    sub.max_delivery_staff = plan_model.max_delivery_staff
    sub.max_customers = plan_model.max_customers
    sub.max_orders_per_month = plan_model.max_orders_per_month
    sub.max_storage_mb = plan_model.max_storage_mb
    sub.max_api_requests = plan_model.max_api_requests
    
    if plan_name == "FREE_TRIAL":
        sub.trial_start_date = date.today()
        sub.trial_end_date = sub.end_date
        
    db.commit()
    db.refresh(sub)
    return sub

@router.post("/subscriptions/{tenant_id}/extend")
def extend_tenant_subscription(
    tenant_id: UUID,
    payload: SubscriptionExtendPayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.subscription import Subscription
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
        
    from datetime import timedelta
    sub.end_date = sub.end_date + timedelta(days=payload.days)
    if sub.plan_name == "FREE_TRIAL":
        sub.trial_end_date = sub.end_date
        
    sub.status = "ACTIVE"
    db.commit()
    db.refresh(sub)
    return sub

@router.post("/subscriptions/{tenant_id}/status")
def update_subscription_status(
    tenant_id: UUID,
    payload: SubscriptionStatusPayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.subscription import Subscription
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
        
    stat = payload.status.upper()
    if stat not in ["ACTIVE", "EXPIRED", "SUSPENDED", "CANCELLED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Choose ACTIVE, EXPIRED, SUSPENDED, or CANCELLED"
        )
        
    sub.status = stat
    db.commit()
    db.refresh(sub)
    return sub

class AnnouncementPayload(BaseModel):
    title: str
    content: str
    status: Optional[str] = "PUBLISHED"
    target_audience: Optional[str] = "ALL"
    target_companies: Optional[str] = None
    scheduled_at: Optional[datetime] = None

class PlatformSettingsUpdatePayload(BaseModel):
    platform_name: Optional[str] = None
    logo_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    sms_api_key: Optional[str] = None
    whatsapp_api_key: Optional[str] = None
    google_maps_api_key: Optional[str] = None
    payment_gateway_client_id: Optional[str] = None
    payment_gateway_secret: Optional[str] = None

@router.get("/audit-logs")
def view_audit_logs(
    tenant_id: Optional[UUID] = None,
    module: Optional[str] = None,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.audit_log import AuditLog
    query = db.query(AuditLog)
    if tenant_id:
        query = query.filter(AuditLog.tenant_id == tenant_id)
    if module:
        query = query.filter(AuditLog.module == module)
    return query.order_by(AuditLog.created_at.desc()).limit(100).all()

@router.post("/announcements")
def create_announcement(
    payload: AnnouncementPayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.announcement import Announcement
    from uuid import uuid4
    ann = Announcement(
        id=uuid4(),
        title=payload.title,
        content=payload.content,
        status=payload.status or "PUBLISHED",
        tenant_id=None,
        target_audience=payload.target_audience or "ALL",
        target_companies=payload.target_companies,
        scheduled_at=payload.scheduled_at or datetime.utcnow()
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann

@router.get("/announcements")
def list_announcements(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.announcement import Announcement
    return db.query(Announcement).filter(Announcement.tenant_id == None).order_by(Announcement.created_at.desc()).all()

@router.delete("/announcements/{id}")
def delete_announcement(
    id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.announcement import Announcement
    ann = db.query(Announcement).filter(Announcement.id == id).first()
    if not ann:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )
    db.delete(ann)
    db.commit()
    return {"success": True, "message": "Announcement deleted successfully"}

@router.get("/settings")
def get_platform_settings(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.platform_settings import PlatformSettings
    settings_obj = db.query(PlatformSettings).first()
    if not settings_obj:
        from uuid import uuid4
        settings_obj = PlatformSettings(
            id=uuid4(),
            platform_name="Laundry SaaS Platform"
        )
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return settings_obj

@router.put("/settings")
def update_platform_settings(
    payload: PlatformSettingsUpdatePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.platform_settings import PlatformSettings
    settings_obj = db.query(PlatformSettings).first()
    if not settings_obj:
        from uuid import uuid4
        settings_obj = PlatformSettings(
            id=uuid4(),
            platform_name="Laundry SaaS Platform"
        )
        db.add(settings_obj)
        
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(settings_obj, k, v)
        
    from app.models.audit_log import AuditLog
    from uuid import uuid4
    audit_log = AuditLog(
        id=uuid4(),
        tenant_id=super_admin.tenant_id,
        user_id=super_admin.id,
        action="Updated platform-wide global configurations",
        module="SETTINGS"
    )
    db.add(audit_log)
        
    db.commit()
    db.refresh(settings_obj)
    return settings_obj

@router.get("/companies/{company_id}/customers")
def get_company_customers(
    company_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.customer import Customer
    return db.query(Customer).filter(Customer.tenant_id == company_id).all()

@router.get("/companies/{company_id}/orders")
def get_company_orders(
    company_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.order import Order
    return db.query(Order).filter(Order.tenant_id == company_id).order_by(Order.created_at.desc()).all()

@router.get("/companies/{company_id}/payments")
def get_company_payments(
    company_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.payment import Payment
    return db.query(Payment).filter(Payment.tenant_id == company_id).order_by(Payment.created_at.desc()).all()


