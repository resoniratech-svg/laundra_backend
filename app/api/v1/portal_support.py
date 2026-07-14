from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from uuid import uuid4, UUID
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.dependencies import get_current_customer
from app.models.customer import Customer
from app.models.customer_support_ticket import CustomerSupportTicket

router = APIRouter()

class CustomerTicketCreate(BaseModel):
    subject: str
    description: str

class CustomerTicketOut(BaseModel):
    id: UUID
    subject: str
    description: str
    status: str
    admin_response: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.post("", response_model=CustomerTicketOut, status_code=status.HTTP_201_CREATED)
def create_customer_ticket(
    payload: CustomerTicketCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    ticket = CustomerSupportTicket(
        id=uuid4(),
        tenant_id=current_customer.tenant_id,
        customer_id=current_customer.id,
        subject=payload.subject,
        description=payload.description,
        status="OPEN"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.get("", response_model=List[CustomerTicketOut])
def get_customer_tickets(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    tickets = db.query(CustomerSupportTicket).filter(
        CustomerSupportTicket.customer_id == current_customer.id
    ).order_by(desc(CustomerSupportTicket.created_at)).all()
    return tickets
