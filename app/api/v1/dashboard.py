from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.order import Order
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.delivery import Delivery
from app.core.tenant import get_current_tenant_id

router = APIRouter()

@router.get("")
def get_dashboard_summary(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    
    # 1. Today's orders count
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = db.query(func.count(Order.id)).filter(
        Order.tenant_id == tenant_id,
        Order.created_at >= today_start
    ).scalar() or 0
    
    # 2. Active customers count (customers who have placed orders)
    active_customers = db.query(func.count(func.distinct(Order.customer_id))).filter(
        Order.tenant_id == tenant_id
    ).scalar() or 0
    
    # 3. Revenue (Total successful payments)
    revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.tenant_id == tenant_id,
        Payment.status == "SUCCESS"
    ).scalar() or Decimal("0.0")
    
    # 4. Pending deliveries (deliveries not completed)
    pending_deliveries = db.query(func.count(Delivery.id)).filter(
        Delivery.tenant_id == tenant_id,
        Delivery.status != "DELIVERED"
    ).scalar() or 0
    
    # 5. Recent payments (last 5)
    recent_payments_query = db.query(
        Payment.id, Payment.amount, Payment.method, Payment.created_at
    ).filter(
        Payment.tenant_id == tenant_id
    ).order_by(Payment.created_at.desc()).limit(5).all()
    
    recent_payments = [
        {
            "id": p[0],
            "amount": p[1],
            "method": p[2],
            "created_at": p[3]
        }
        for p in recent_payments_query
    ]
    
    return {
        "today_orders": today_orders,
        "active_customers": active_customers,
        "revenue": revenue,
        "pending_deliveries": pending_deliveries,
        "recent_payments": recent_payments
    }

@router.get("/orders-summary")
def get_orders_summary(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    status_counts = db.query(
        Order.status, func.count(Order.id)
    ).filter(
        Order.tenant_id == tenant_id
    ).group_by(Order.status).all()
    return {status: count for status, count in status_counts}

@router.get("/revenue")
def get_revenue(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    total_rev = db.query(func.sum(Payment.amount)).filter(
        Payment.tenant_id == tenant_id,
        Payment.status == "SUCCESS"
    ).scalar() or Decimal("0.0")
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_rev = db.query(func.sum(Payment.amount)).filter(
        Payment.tenant_id == tenant_id,
        Payment.status == "SUCCESS",
        Payment.created_at >= today_start
    ).scalar() or Decimal("0.0")
    
    return {
        "total_revenue": total_rev,
        "today_revenue": today_rev
    }

@router.get("/customers")
def get_customers(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    total_cust = db.query(func.count(Customer.id)).filter(Customer.tenant_id == tenant_id).scalar() or 0
    return {"total_customers": total_cust}

@router.get("/delivery")
def get_delivery(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    pending = db.query(func.count(Delivery.id)).filter(
        Delivery.tenant_id == tenant_id,
        Delivery.status != "DELIVERED"
    ).scalar() or 0
    completed = db.query(func.count(Delivery.id)).filter(
        Delivery.tenant_id == tenant_id,
        Delivery.status == "DELIVERED"
    ).scalar() or 0
    return {
        "pending_deliveries": pending,
        "completed_deliveries": completed
    }
