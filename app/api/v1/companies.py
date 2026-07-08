from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from datetime import date, timedelta
from typing import List

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.subscription import Subscription
from app.schemas.company import CompanyCreate, CompanyOut, CompanySettingsUpdate
from app.core.security import get_password_hash

router = APIRouter()

def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SaaS super administrators can access this resource"
        )
    return current_user

@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    if payload.email:
        existing = db.query(Company).filter(Company.email == payload.email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
            
    if payload.subdomain:
        existing_sub = db.query(Company).filter(Company.subdomain == payload.subdomain).first()
        if existing_sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subdomain already taken"
            )
            
    company_id = uuid4()
    company = Company(
        id=company_id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        password=get_password_hash(payload.password),
        subdomain=payload.subdomain,
        logo=payload.logo,
        address=payload.address,
        status="ACTIVE"
    )
    db.add(company)
    
    admin_user = User(
        id=uuid4(),
        tenant_id=company_id,
        name=payload.name + " Admin",
        phone=payload.phone,
        email=payload.email,
        password=get_password_hash(payload.password),
        role="ADMIN",
        status="ACTIVE"
    )
    db.add(admin_user)
    
    sub = Subscription(
        id=uuid4(),
        tenant_id=company_id,
        plan_name="FREE_TRIAL",
        status="ACTIVE",
        max_users=5,
        max_orders=100,
        end_date=date.today() + timedelta(days=14),
        trial_start_date=date.today(),
        trial_end_date=date.today() + timedelta(days=14)
    )
    db.add(sub)
    
    from app.models.audit_log import AuditLog
    audit_log = AuditLog(
        id=uuid4(),
        tenant_id=company_id,
        user_id=super_admin.id,
        action=f"Created company {company.name} and initialized trial subscription",
        module="COMPANY"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(company)
    return company

@router.get("/me", response_model=CompanyOut)
def get_company_me(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.id == current_user.tenant_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    return company

@router.patch("/me/settings", response_model=CompanyOut)
def update_company_settings(
    payload: CompanySettingsUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.id == current_user.tenant_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    if payload.delivery_commission_percent is not None:
        company.delivery_commission_percent = payload.delivery_commission_percent
        
    db.commit()
    db.refresh(company)
    return company

@router.get("/public", response_model=List[CompanyOut])
def list_companies_public(
    db: Session = Depends(get_db)
):
    """
    Public endpoint to list active companies.
    Used by customers during self-registration to select their laundry company.
    """
    return db.query(Company).filter(Company.status == "ACTIVE").all()

@router.post("/{company_id}/services/import")
def import_services(
    company_id: UUID,
    file: UploadFile = File(...),
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.services.import_service import ImportService
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )
    
    return ImportService.import_service_catalog(db, tenant_id=company_id, file=file)
