from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from uuid import uuid4, UUID

from app.core.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationOut

router = APIRouter()

@router.post("", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    notification = Notification(
        id=uuid4(),
        tenant_id=current_admin.tenant_id,
        user_id=payload.user_id,
        title=payload.title,
        message=payload.message
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

@router.get("", response_model=List[NotificationOut])
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Notification).filter(
        Notification.tenant_id == current_user.tenant_id
    )
    
    # If not admin, only show notifications targeted to them or to everyone (user_id is None)
    if current_user.role != "COMPANY_ADMIN":
        query = query.filter(
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None))
        )
        
    return query.order_by(desc(Notification.created_at)).all()

@router.patch("/{id}/read", response_model=NotificationOut)
def mark_as_read(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    notification = db.query(Notification).filter(
        Notification.id == id,
        Notification.tenant_id == current_user.tenant_id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
        
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification

@router.delete("/{id}")
def delete_notification(
    id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    notification = db.query(Notification).filter(
        Notification.id == id,
        Notification.tenant_id == current_admin.tenant_id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
        
    db.delete(notification)
    db.commit()
    return {"success": True, "message": "Notification deleted successfully"}

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class CompanyAnnouncementPayload(BaseModel):
    title: str
    content: str
    status: Optional[str] = "PUBLISHED"
    target_audience: Optional[str] = "ALL"
    scheduled_at: Optional[datetime] = None

@router.post("/announcements")
def create_company_announcement(
    payload: CompanyAnnouncementPayload,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    from app.models.announcement import Announcement
    
    if payload.target_audience not in ["CUSTOMERS", "DELIVERY_BOYS", "ALL"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid target_audience. Must be CUSTOMERS, DELIVERY_BOYS, or ALL"
        )
        
    ann = Announcement(
        id=uuid4(),
        title=payload.title,
        content=payload.content,
        status=payload.status or "PUBLISHED",
        tenant_id=current_admin.tenant_id,
        target_audience=payload.target_audience or "ALL",
        scheduled_at=payload.scheduled_at or datetime.utcnow()
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann

@router.get("/announcements")
def list_company_announcements(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    from app.models.announcement import Announcement
    own_anns = db.query(Announcement).filter(
        Announcement.tenant_id == current_admin.tenant_id
    ).all()
    
    platform_anns = db.query(Announcement).filter(
        Announcement.tenant_id == None,
        Announcement.target_audience.in_(["ADMINS", "ALL"])
    ).all()
    
    return sorted(own_anns + platform_anns, key=lambda x: x.created_at, reverse=True)
