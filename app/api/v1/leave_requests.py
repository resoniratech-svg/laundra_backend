from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from uuid import UUID
from pydantic import BaseModel
from datetime import date, datetime

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.leave_request import LeaveRequest

router = APIRouter()

class LeaveRequestOut(BaseModel):
    id: UUID
    delivery_boy_name: str
    delivery_boy_email: str
    start_date: date
    end_date: date
    reason: str
    status: str
    admin_comment: str | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True

class LeaveRequestStatusUpdate(BaseModel):
    status: str
    admin_comment: str | None = None

@router.get("", response_model=List[LeaveRequestOut])
def get_leave_requests(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    leave_requests = (
        db.query(LeaveRequest, User)
        .join(User, LeaveRequest.user_id == User.id)
        .filter(LeaveRequest.tenant_id == current_admin.tenant_id)
        .order_by(desc(LeaveRequest.created_at))
        .all()
    )

    result = []
    for lr, user in leave_requests:
        result.append(LeaveRequestOut(
            id=lr.id,
            delivery_boy_name=user.name or "Unknown",
            delivery_boy_email=user.email or "Unknown",
            start_date=lr.start_date,
            end_date=lr.end_date,
            reason=lr.reason,
            status=lr.status,
            admin_comment=lr.admin_comment,
            updated_at=lr.updated_at
        ))
    
    return result

@router.patch("/{leave_id}/status")
def update_leave_request_status(
    leave_id: UUID,
    payload: LeaveRequestStatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    leave_request = db.query(LeaveRequest).filter(
        LeaveRequest.id == leave_id,
        LeaveRequest.tenant_id == current_admin.tenant_id
    ).first()

    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    if payload.status not in ["APPROVED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status"
        )

    leave_request.status = payload.status
    if payload.admin_comment:
        leave_request.admin_comment = payload.admin_comment
        
    db.commit()
    return {"message": f"Leave request {payload.status.lower()} successfully."}
