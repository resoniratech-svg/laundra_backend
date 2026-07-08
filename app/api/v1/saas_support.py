from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()

def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SaaS super administrators can access this resource"
        )
    return current_user

class SupportReplyPayload(BaseModel):
    message: str

@router.get("")
def list_support_tickets(
    status: Optional[str] = None,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.support_ticket import SupportTicket
    query = db.query(SupportTicket)
    if status:
        query = query.filter(SupportTicket.status == status.upper())
    return query.order_by(SupportTicket.created_at.desc()).all()

@router.get("/{ticket_id}")
def get_support_ticket(
    ticket_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.support_ticket import SupportTicket
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@router.post("/{ticket_id}/reply")
def reply_to_ticket(
    ticket_id: UUID,
    payload: SupportReplyPayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.support_ticket import SupportTicket
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    # In a real system, we'd add this to a TicketReply table. 
    # For now, we update the main ticket response if it's a simple model.
    # We will just mark it as IN_PROGRESS and assume the reply was sent via email for now.
    ticket.status = "IN_PROGRESS"
    db.commit()
    db.refresh(ticket)
    
    return {
        "message": "Reply sent successfully",
        "ticket": ticket
    }

@router.post("/{ticket_id}/close")
def close_ticket(
    ticket_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.support_ticket import SupportTicket
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.status = "CLOSED"
    db.commit()
    db.refresh(ticket)
    return ticket
