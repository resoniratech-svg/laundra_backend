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

def verify_company_admin(
    company_id: UUID,
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role == "SUPER_ADMIN":
        return current_user
    if current_user.role == "ADMIN" and current_user.tenant_id == company_id:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only SaaS super administrators or the company administrator can manage these services"
    )

@router.post("/{company_id}/services/import")
def import_services(
    company_id: UUID,
    file: UploadFile = File(...),
    admin_user: User = Depends(verify_company_admin),
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


from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

class ManualServiceCreate(BaseModel):
    name: str
    category: str
    price: Decimal
    express_price: Optional[Decimal] = None

class ManualServiceUpdate(BaseModel):
    name: str
    category: str
    price: Decimal
    express_price: Optional[Decimal] = None

@router.get("/{company_id}/services")
def get_company_services(
    company_id: UUID,
    admin_user: User = Depends(verify_company_admin),
    db: Session = Depends(get_db)
):
    from app.models.service import Service
    return db.query(Service).filter(Service.tenant_id == company_id).order_by(Service.name, Service.category).all()

@router.post("/{company_id}/services")
def add_manual_service(
    company_id: UUID,
    payload: ManualServiceCreate,
    admin_user: User = Depends(verify_company_admin),
    db: Session = Depends(get_db)
):
    from app.models.service import Service
    existing = db.query(Service).filter(
        Service.tenant_id == company_id,
        Service.name == payload.name,
        Service.category == payload.category
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Service with this name and category already exists")
    
    new_service = Service(
        id=uuid4(),
        tenant_id=company_id,
        name=payload.name,
        category=payload.category,
        unit="PIECE",
        price=payload.price,
        express_price=payload.express_price
    )
    db.add(new_service)
    db.commit()
    return {"message": "Service created successfully"}

@router.put("/{company_id}/services/{service_id}")
def update_manual_service(
    company_id: UUID,
    service_id: UUID,
    payload: ManualServiceUpdate,
    admin_user: User = Depends(verify_company_admin),
    db: Session = Depends(get_db)
):
    from app.models.service import Service
    service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == company_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    service.name = payload.name
    service.category = payload.category
    service.price = payload.price
    service.express_price = payload.express_price
    db.commit()
    return {"message": "Service updated successfully"}

@router.delete("/{company_id}/services/{service_id}")
def delete_manual_service(
    company_id: UUID,
    service_id: UUID,
    admin_user: User = Depends(verify_company_admin),
    db: Session = Depends(get_db)
):
    from app.models.service import Service
    service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == company_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    db.delete(service)
    db.commit()
    return {"message": "Service deleted successfully"}

@router.get("/{company_id}/services/export")
def export_services(
    company_id: UUID,
    admin_user: User = Depends(verify_company_admin),
    db: Session = Depends(get_db)
):
    from app.models.service import Service
    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse

    services = db.query(Service).filter(Service.tenant_id == company_id).all()
    if not services:
        raise HTTPException(status_code=404, detail="No services found to export")

    categories = sorted(list(set(s.category for s in services if s.category)))
    
    rows = {}
    for s in services:
        if s.name not in rows:
            rows[s.name] = {}
        rows[s.name][f"{s.category} Normal"] = s.price
        rows[s.name][f"{s.category} Express"] = s.express_price

    data = []
    for idx, (name, prices) in enumerate(rows.items(), 1):
        row_dict = {
            "Sl No": idx,
            "Item Description": name
        }
        for cat in categories:
            row_dict[f"{cat} Normal"] = prices.get(f"{cat} Normal", None)
            row_dict[f"{cat} Express"] = prices.get(f"{cat} Express", None)
        data.append(row_dict)

    df = pd.DataFrame(data)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Catalog")
    buffer.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="service_catalog_{company_id}.xlsx"'
    }
    return StreamingResponse(buffer, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
