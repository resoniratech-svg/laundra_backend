from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.models.announcement import Announcement
from app.models.user import User
from app.models.customer import Customer
from app.dependencies import get_current_admin, get_current_customer, get_current_delivery_boy, get_current_admin_or_cashier

router = APIRouter()

class AnnouncementOut(BaseModel):
    id: UUID
    title: str
    content: str
    status: str
    tenant_id: Optional[UUID] = None
    target_audience: str
    target_companies: Optional[str] = None
    scheduled_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class CompanyAnnouncementCreate(BaseModel):
    title: str
    content: str
    target_audience: str = "ALL"  # ALL, CUSTOMERS, DELIVERY_BOYS

@router.post("/company")
def create_company_announcement(
    payload: CompanyAnnouncementCreate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    if not payload.title or not payload.content:
        raise HTTPException(status_code=400, detail="Title and content are required")

    from uuid import uuid4
    ann = Announcement(
        id=uuid4(),
        title=payload.title,
        content=payload.content,
        status="PUBLISHED",
        tenant_id=current_admin.tenant_id,
        target_audience=payload.target_audience.upper(),
        target_companies=str(current_admin.tenant_id),
        scheduled_at=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return {"message": "Announcement published successfully", "announcement": ann}

@router.get("/company", response_model=List[AnnouncementOut])
def list_company_announcements(
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    return db.query(Announcement).filter(
        Announcement.tenant_id == current_admin.tenant_id
    ).order_by(Announcement.created_at.desc()).all()

@router.delete("/company/{announcement_id}")
def delete_company_announcement(
    announcement_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    ann = db.query(Announcement).filter(
        Announcement.id == announcement_id,
        Announcement.tenant_id == current_admin.tenant_id
    ).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    db.delete(ann)
    db.commit()
    return {"message": "Announcement deleted successfully"}

@router.get("/admin", response_model=List[AnnouncementOut])
def get_admin_announcements(
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    """Get announcements for company admins"""
    tenant_id_str = str(current_admin.tenant_id)
    announcements = db.query(Announcement).filter(
        Announcement.status == "PUBLISHED",
        Announcement.target_audience.in_(["ALL", "ADMINS"]),
        or_(
            Announcement.target_companies == None,
            Announcement.target_companies.contains(tenant_id_str)
        )
    ).order_by(Announcement.created_at.desc()).all()
    return announcements

@router.get("/staff", response_model=List[AnnouncementOut])
def get_staff_announcements(
    current_staff: User = Depends(get_current_delivery_boy),
    db: Session = Depends(get_db)
):
    """Get announcements for delivery staff"""
    tenant_id_str = str(current_staff.tenant_id)
    announcements = db.query(Announcement).filter(
        Announcement.status == "PUBLISHED",
        Announcement.target_audience.in_(["ALL", "DELIVERY_BOYS"]),
        or_(
            Announcement.tenant_id == current_staff.tenant_id,
            Announcement.target_companies == None,
            Announcement.target_companies.contains(tenant_id_str)
        )
    ).order_by(Announcement.created_at.desc()).all()
    return announcements

@router.get("/customer", response_model=List[AnnouncementOut])
def get_customer_announcements(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Get announcements for customers"""
    tenant_id_str = str(current_customer.tenant_id)
    announcements = db.query(Announcement).filter(
        Announcement.status == "PUBLISHED",
        Announcement.target_audience.in_(["ALL", "CUSTOMERS"]),
        or_(
            Announcement.tenant_id == current_customer.tenant_id,
            Announcement.target_companies == None,
            Announcement.target_companies.contains(tenant_id_str)
        )
    ).order_by(Announcement.created_at.desc()).all()
    return announcements
