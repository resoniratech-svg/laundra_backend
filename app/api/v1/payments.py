from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.dependencies import get_current_user, get_current_admin_or_cashier
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services.payment_service import PaymentService
from app.repositories.payment_repository import PaymentRepository

router = APIRouter()
payment_repo = PaymentRepository()

class PaymentStatusUpdate(BaseModel):
    status: str  # SUCCESS, FAILED, PENDING

@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_in: PaymentCreate,
    current_user: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    return PaymentService.create_payment(
        db,
        order_id=payment_in.order_id,
        amount=payment_in.amount,
        method=payment_in.method,
        delivery_boy_id=payment_in.delivery_boy_id,
        delivery_boy_commission=payment_in.delivery_boy_commission,
        tenant_id=current_user.tenant_id
    )

@router.get("", response_model=List[PaymentOut])
def list_payments(
    current_user: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    return payment_repo.get_multi(db)

@router.get("/{id}", response_model=PaymentOut)
def get_payment_details(
    id: UUID,
    current_user: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    payment = payment_repo.get(db, id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment record not found"
        )
    return payment

@router.patch("/{id}", response_model=PaymentOut)
def update_payment_status(
    id: UUID,
    payload: PaymentStatusUpdate,
    current_user: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    payment = payment_repo.get(db, id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment record not found"
        )
    payment.status = payload.status
    db.commit()
    db.refresh(payment)
    return payment

@router.post("/{id}/refund", response_model=PaymentOut)
def refund_payment(
    id: UUID,
    current_user: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    payment = payment_repo.get(db, id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment record not found"
        )
    
    if payment.status == "REFUNDED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment is already refunded"
        )
        
    payment.status = "REFUNDED"
    
    from app.models.order import Order
    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if order:
        order.payment_status = "REFUNDED"
        
    db.commit()
    db.refresh(payment)
    return payment
