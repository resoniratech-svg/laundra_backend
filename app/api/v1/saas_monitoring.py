from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

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

@router.get("/{tenant_id}/customers")
def get_company_customers(
    tenant_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.customer import Customer
    return db.query(Customer).filter(Customer.tenant_id == tenant_id).all()

@router.get("/{tenant_id}/cashiers")
def get_company_cashiers(
    tenant_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.user import User
    return db.query(User).filter(User.tenant_id == tenant_id, User.role == "CASHIER").all()

@router.get("/{tenant_id}/delivery-staff")
def get_company_delivery_staff(
    tenant_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.user import User
    return db.query(User).filter(User.tenant_id == tenant_id, User.role == "DELIVERY_BOY").all()

@router.get("/{tenant_id}/orders")
def get_company_orders(
    tenant_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.order import Order
    return db.query(Order).filter(Order.tenant_id == tenant_id).order_by(Order.created_at.desc()).limit(100).all()

@router.get("/{tenant_id}/payments")
def get_company_payments(
    tenant_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from app.models.payment import Payment
    return db.query(Payment).filter(Payment.tenant_id == tenant_id).order_by(Payment.payment_date.desc()).limit(100).all()
