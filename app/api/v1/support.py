from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4, UUID
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.support_ticket import SupportTicket
from app.core.tenant import get_current_tenant_id
from datetime import datetime

router = APIRouter()

class TicketCreate(BaseModel):
    subject: str
    description: str
    priority: str = "MEDIUM" # LOW, MEDIUM, HIGH

class TicketRespond(BaseModel):
    response: str

class SupportTicketOut(BaseModel):
    id: UUID
    tenant_id: UUID
    subject: str
    description: str
    status: str
    priority: str
    internal_notes: Optional[str] = None
    created_at: datetime
    company_name: Optional[str] = None
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    admin_phone: Optional[str] = None
    admin_address: Optional[str] = None
    
    class Config:
        from_attributes = True

@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tenant_id = current_user.tenant_id
    
    ticket = SupportTicket(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_user.id,
        subject=payload.subject,
        description=payload.description,
        status="OPEN",
        priority=payload.priority.upper()
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.get("/tickets", response_model=List[SupportTicketOut])
def list_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(SupportTicket, Company, User).outerjoin(
        Company, SupportTicket.tenant_id == Company.id
    ).outerjoin(
        User, SupportTicket.user_id == User.id
    )
    
    if current_user.role != "SUPER_ADMIN":
        tenant_id = current_user.tenant_id
        query = query.filter(SupportTicket.tenant_id == tenant_id)
        
    results = query.order_by(SupportTicket.created_at.desc()).all()
    
    out_list = []
    for ticket, company, user in results:
        out_list.append(SupportTicketOut(
            id=ticket.id,
            tenant_id=ticket.tenant_id,
            subject=ticket.subject,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            internal_notes=ticket.internal_notes,
            created_at=ticket.created_at,
            company_name=company.name if company else None,
            admin_name=user.name if user else None,
            admin_email=user.email if user else None,
            admin_phone=user.phone if user else None,
            admin_address=user.address if user else None
        ))
        
    return out_list

@router.get("/tickets/{id}")
def get_ticket(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "SUPER_ADMIN":
        ticket = db.query(SupportTicket).filter(SupportTicket.id == id).first()
    else:
        tenant_id = current_user.tenant_id
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support ticket not found"
        )
    return ticket

@router.post("/tickets/{id}/respond")
def respond_ticket(
    id: UUID,
    payload: TicketRespond,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Super Admin and Admin can respond
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to respond to support tickets"
        )
        
    if current_user.role == "SUPER_ADMIN":
        ticket = db.query(SupportTicket).filter(SupportTicket.id == id).first()
    else:
        tenant_id = current_user.tenant_id
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support ticket not found"
        )
        
    # Set the response in internal_notes and update status
    ticket.status = "RESPONDED"
    ticket.internal_notes = payload.response
    
    db.commit()
    db.refresh(ticket)
    return {"message": "Response submitted successfully", "ticket": ticket}

@router.post("/tickets/{id}/close")
def close_ticket(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to close support tickets"
        )
        
    if current_user.role == "SUPER_ADMIN":
        ticket = db.query(SupportTicket).filter(SupportTicket.id == id).first()
    else:
        tenant_id = current_user.tenant_id
        ticket = db.query(SupportTicket).filter(
            SupportTicket.id == id,
            SupportTicket.tenant_id == tenant_id
        ).first()
        
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support ticket not found"
        )
        
    ticket.status = "CLOSED"
    db.commit()
    db.refresh(ticket)
    return {"message": "Ticket closed successfully", "ticket": ticket}
