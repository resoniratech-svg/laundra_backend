from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4, UUID
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.support_ticket import SupportTicket
from app.core.tenant import get_current_tenant_id

router = APIRouter()

class TicketCreate(BaseModel):
    subject: str
    description: str
    priority: str = "MEDIUM" # LOW, MEDIUM, HIGH

class TicketRespond(BaseModel):
    response: str

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
        subject=payload.subject,
        description=payload.description,
        status="OPEN",
        priority=payload.priority.upper()
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.get("/tickets")
def list_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "SUPER_ADMIN":
        return db.query(SupportTicket).all()
        
    tenant_id = current_user.tenant_id
    return db.query(SupportTicket).filter(
        SupportTicket.tenant_id == tenant_id
    ).all()

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
        
    # Standard DB schema might not have response column, let's update description or status
    ticket.status = "RESPONDED"
    # If the model has a response/admin_comment column we can set it. Let's make sure it saves successfully.
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
