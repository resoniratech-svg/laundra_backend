"""
Subscription limit enforcement helpers.
Call these before creating users, customers, or orders to ensure the
company has not exceeded their plan limits.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import date, datetime


def get_subscription(db: Session, tenant_id: UUID):
    """Return the active subscription for a tenant or raise 403."""
    from app.models.subscription import Subscription
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No subscription found for this company."
        )
    if sub.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your company subscription is not active."
        )
    if sub.end_date and sub.end_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your company subscription has expired. Please renew to continue."
        )
    return sub


def check_admin_limit(db: Session, tenant_id: UUID):
    from app.models.user import User
    from app.models.subscription import Subscription
    sub = get_subscription(db, tenant_id)
    current = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "ADMIN"
    ).count()
    if current >= sub.max_admins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin limit reached ({current}/{sub.max_admins}). Upgrade your plan to add more admins."
        )


def check_cashier_limit(db: Session, tenant_id: UUID):
    from app.models.user import User
    from app.models.subscription import Subscription
    sub = get_subscription(db, tenant_id)
    current = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "CASHIER"
    ).count()
    if current >= sub.max_cashiers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cashier limit reached ({current}/{sub.max_cashiers}). Upgrade your plan to add more cashiers."
        )


def check_delivery_limit(db: Session, tenant_id: UUID):
    from app.models.user import User
    sub = get_subscription(db, tenant_id)
    current = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "DELIVERY_BOY"
    ).count()
    if current >= sub.max_delivery_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Delivery staff limit reached ({current}/{sub.max_delivery_staff}). Upgrade your plan to add more delivery staff."
        )


def check_customer_limit(db: Session, tenant_id: UUID):
    from app.models.customer import Customer
    sub = get_subscription(db, tenant_id)
    current = db.query(Customer).filter(Customer.tenant_id == tenant_id).count()
    if current >= sub.max_customers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Customer limit reached ({current}/{sub.max_customers}). Upgrade your plan to add more customers."
        )


def check_monthly_orders_limit(db: Session, tenant_id: UUID):
    from app.models.order import Order
    sub = get_subscription(db, tenant_id)
    today = date.today()
    month_start = today.replace(day=1)
    current = db.query(Order).filter(
        Order.tenant_id == tenant_id,
        Order.created_at >= datetime.combine(month_start, datetime.min.time())
    ).count()
    if current >= sub.max_orders_per_month:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly order limit reached ({current}/{sub.max_orders_per_month}). Upgrade your plan for more orders."
        )
