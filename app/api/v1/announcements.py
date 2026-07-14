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
            Announcement.target_companies == None,
            Announcement.target_companies.contains(tenant_id_str)
        )
    ).order_by(Announcement.created_at.desc()).all()
    return announcements
