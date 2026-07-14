from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from uuid import UUID
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.customer import Customer
from app.models.customer_support_ticket import CustomerSupportTicket

router = APIRouter()

class AdminCustomerTicketOut(BaseModel):
    id: UUID
    subject: str
    description: str
    status: str
    admin_response: Optional[str] = None
    created_at: datetime
    customer_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    sender_phone: Optional[str] = None
    sender_address: Optional[str] = None
    sender_type: str
    
    class Config:
        from_attributes = True

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    admin_response: Optional[str] = None

@router.get("", response_model=List[AdminCustomerTicketOut])
def get_admin_customer_tickets(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tickets = db.query(CustomerSupportTicket, Customer, User).outerjoin(
        Customer, CustomerSupportTicket.customer_id == Customer.id
    ).outerjoin(
        User, CustomerSupportTicket.user_id == User.id
    ).filter(
        CustomerSupportTicket.tenant_id == current_admin.tenant_id
    ).order_by(desc(CustomerSupportTicket.created_at)).all()
    
    result = []
    for ticket, customer, user in tickets:
        if user:
            sender_name = user.name
            sender_email = user.email
            sender_phone = user.phone
            sender_address = user.address
            sender_type = "Delivery Staff" if user.role in ["DELIVERY_BOY", "DELIVERY_STAFF", "Delivery Staff", "Delivery Boy"] else "Staff"
        elif customer:
            sender_name = customer.name
            sender_email = customer.email
            sender_phone = customer.phone
            sender_address = customer.address
            sender_type = "Customer"
        else:
            sender_name = "Unknown"
            sender_email = ""
            sender_phone = ""
            sender_address = ""
            sender_type = "Unknown"

        result.append(AdminCustomerTicketOut(
            id=ticket.id,
            subject=ticket.subject,
            description=ticket.description,
            status=ticket.status,
            admin_response=ticket.admin_response,
            created_at=ticket.created_at,
            customer_id=ticket.customer_id,
            user_id=ticket.user_id,
            sender_name=sender_name,
            sender_email=sender_email,
            sender_phone=sender_phone,
            sender_address=sender_address,
            sender_type=sender_type
        ))
        
    return result

@router.patch("/{ticket_id}", response_model=AdminCustomerTicketOut)
def update_admin_customer_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    ticket = db.query(CustomerSupportTicket).filter(
        CustomerSupportTicket.id == ticket_id,
        CustomerSupportTicket.tenant_id == current_admin.tenant_id
    ).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    if payload.status:
        ticket.status = payload.status
    if payload.admin_response:
        ticket.admin_response = payload.admin_response
        
    db.commit()
    db.refresh(ticket)
    
    customer = db.query(Customer).filter(Customer.id == ticket.customer_id).first()
    user = db.query(User).filter(User.id == ticket.user_id).first()
    
    if user:
        sender_name = user.name
        sender_email = user.email
        sender_phone = user.phone
        sender_address = user.address
        sender_type = "Delivery Staff" if user.role in ["DELIVERY_BOY", "DELIVERY_STAFF", "Delivery Staff", "Delivery Boy"] else "Staff"
    elif customer:
        sender_name = customer.name
        sender_email = customer.email
        sender_phone = customer.phone
        sender_address = customer.address
        sender_type = "Customer"
    else:
        sender_name = "Unknown"
        sender_email = ""
        sender_phone = ""
        sender_address = ""
        sender_type = "Unknown"
    
    return AdminCustomerTicketOut(
        id=ticket.id,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        admin_response=ticket.admin_response,
        created_at=ticket.created_at,
        customer_id=ticket.customer_id,
        user_id=ticket.user_id,
        sender_name=sender_name,
        sender_email=sender_email,
        sender_phone=sender_phone,
        sender_address=sender_address,
        sender_type=sender_type
    )
