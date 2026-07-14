from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4, UUID
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.delivery import Delivery
from app.models.customer_support_ticket import CustomerSupportTicket

router = APIRouter()

class GPSLocationPayload(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None

class LeaveApplyPayload(BaseModel):
    start_date: date
    end_date: date
    reason: str

@router.post("/attendance/clock-in")
def clock_in(
    payload: GPSLocationPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can log attendance"
        )
        
    # Check if already clocked in today (without clocking out)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    existing = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.clock_in >= today_start,
        Attendance.clock_out == None
    ).first()
    
    if existing:
        return {"message": "Already clocked in", "attendance": existing}
        
    att = Attendance(
        id=uuid4(),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        clock_in=datetime.utcnow(),
        gps_lat_in=payload.lat,
        gps_lng_in=payload.lng
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"message": "Clocked in successfully", "attendance": att}

@router.post("/attendance/clock-out")
def clock_out(
    payload: GPSLocationPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can log attendance"
        )
        
    # Find latest active clock in
    att = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.clock_out == None
    ).order_by(Attendance.clock_in.desc()).first()
    
    if not att:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must clock in before clocking out."
        )
        
    att.clock_out = datetime.utcnow()
    att.gps_lat_out = payload.lat;
    att.gps_lng_out = payload.lng;
    db.commit()
    db.refresh(att)
    return {"message": "Clocked out successfully", "attendance": att}

@router.post("/leaves")
def apply_leave(
    payload: LeaveApplyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can apply for leaves"
        )
        
    lr = LeaveRequest(
        id=uuid4(),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
        status="PENDING"
    )
    db.add(lr)
    db.commit()
    db.refresh(lr)
    return {"message": "Leave request submitted successfully", "leave_request": lr}

@router.get("/leaves")
def list_my_leaves(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can list leaves"
        )
        
    return db.query(LeaveRequest).filter(LeaveRequest.user_id == current_user.id).all()

@router.get("/earnings")
def get_earnings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can access earnings metrics"
        )
        
    # Multiplied by $5.0 per completed delivery
    PAYOUT_RATE = 5.0
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=datetime.utcnow().weekday())
    month_start = today_start.replace(day=1)
    
    from sqlalchemy import func
    from app.models.payment import Payment

    today_count = db.query(Delivery).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.status == "DELIVERED",
        Delivery.updated_at >= today_start
    ).count()
    
    week_count = db.query(Delivery).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.status == "DELIVERED",
        Delivery.updated_at >= week_start
    ).count()
    
    month_count = db.query(Delivery).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.status == "DELIVERED",
        Delivery.updated_at >= month_start
    ).count()
    
    total_completed = db.query(Delivery).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.status == "DELIVERED"
    ).count()
    
    # Calculate Commissions from Cash Payments
    today_comm = db.query(func.sum(Payment.delivery_boy_commission)).filter(
        Payment.delivery_boy_id == current_user.id,
        Payment.created_at >= today_start
    ).scalar() or 0.0

    week_comm = db.query(func.sum(Payment.delivery_boy_commission)).filter(
        Payment.delivery_boy_id == current_user.id,
        Payment.created_at >= week_start
    ).scalar() or 0.0
    
    month_comm = db.query(func.sum(Payment.delivery_boy_commission)).filter(
        Payment.delivery_boy_id == current_user.id,
        Payment.created_at >= month_start
    ).scalar() or 0.0

    return {
        "today_earnings": float((today_count * PAYOUT_RATE) + float(today_comm)),
        "weekly_earnings": float((week_count * PAYOUT_RATE) + float(week_comm)),
        "monthly_earnings": float((month_count * PAYOUT_RATE) + float(month_comm)),
        "completed_deliveries_count": total_completed
    }

@router.get("/announcements")
def get_staff_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can access staff announcements"
        )
        
    from app.models.announcement import Announcement
    
    company_anns = db.query(Announcement).filter(
        Announcement.tenant_id == current_user.tenant_id,
        Announcement.status == "PUBLISHED",
        Announcement.target_audience.in_(["DELIVERY_BOYS", "ALL"])
    ).all()
    
    super_anns_query = db.query(Announcement).filter(
        Announcement.tenant_id == None,
        Announcement.status == "PUBLISHED",
        Announcement.target_audience.in_(["DELIVERY_BOYS", "ALL"])
    ).all()
    
    user_tenant_str = str(current_user.tenant_id)
    valid_super_anns = []
    for ann in super_anns_query:
        if not ann.target_companies:
            valid_super_anns.append(ann)
        else:
            targets = [t.strip() for t in ann.target_companies.split(",") if t.strip()]
            if user_tenant_str in targets:
                valid_super_anns.append(ann)
                
    return sorted(company_anns + valid_super_anns, key=lambda x: x.scheduled_at, reverse=True)


class MobileStaffTicketCreate(BaseModel):
    subject: str
    description: str

class MobileStaffTicketOut(BaseModel):
    id: UUID
    subject: str
    description: str
    status: str
    admin_response: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.post("/support-tickets", response_model=MobileStaffTicketOut, status_code=status.HTTP_201_CREATED)
def create_staff_ticket(
    payload: MobileStaffTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["DELIVERY_BOY", "DELIVERY_STAFF", "Delivery Boy", "Delivery Staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can raise support tickets"
        )
        
    ticket = CustomerSupportTicket(
        id=uuid4(),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject=payload.subject,
        description=payload.description,
        status="OPEN"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    # We map UUID to str just to match schema
    return ticket

@router.get("/support-tickets", response_model=List[MobileStaffTicketOut])
def get_staff_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["DELIVERY_BOY", "DELIVERY_STAFF", "Delivery Boy", "Delivery Staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery staff can view support tickets"
        )
        
    tickets = db.query(CustomerSupportTicket).filter(
        CustomerSupportTicket.user_id == current_user.id
    ).order_by(CustomerSupportTicket.created_at.desc()).all()
    
    return tickets
