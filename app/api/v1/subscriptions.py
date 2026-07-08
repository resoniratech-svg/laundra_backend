from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
from pydantic import BaseModel
from datetime import date, timedelta

from app.core.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.subscription import Subscription
from app.core.tenant import get_current_tenant_id

router = APIRouter()

class SubscriptionUpgrade(BaseModel):
    plan_name: str # STARTER, PROFESSIONAL, ENTERPRISE

@router.post("", response_model=dict)
def initialize_subscription(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    existing = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id
    ).first()
    if existing:
        return {"message": "Subscription already initialized", "subscription": existing}
        
    sub = Subscription(
        id=uuid4(),
        tenant_id=tenant_id,
        plan_name="FREE_TRIAL",
        status="ACTIVE",
        max_users=5,
        max_orders=100,
        end_date=date.today() + timedelta(days=30)
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {"message": "Free trial initialized successfully", "subscription": sub}

@router.get("/current")
def get_current_subscription(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id
    ).first()
    if not sub:
        sub = Subscription(
            id=uuid4(),
            tenant_id=tenant_id,
            plan_name="FREE_TRIAL",
            status="ACTIVE",
            max_users=5,
            max_orders=100,
            end_date=date.today() + timedelta(days=30)
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub

@router.put("/upgrade")
def upgrade_subscription(
    payload: SubscriptionUpgrade,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    tenant_id = get_current_tenant_id()
    sub = db.query(Subscription).filter(
        Subscription.tenant_id == tenant_id
    ).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found. Initialize trial first."
        )
        
    plan = payload.plan_name.upper()
    if plan not in ["STARTER", "PROFESSIONAL", "ENTERPRISE"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan name. Choose STARTER, PROFESSIONAL, or ENTERPRISE"
        )
        
    if plan == "STARTER":
        sub.plan_name = "STARTER"
        sub.max_users = 10
        sub.max_orders = 500
        sub.end_date = date.today() + timedelta(days=365)
    elif plan == "PROFESSIONAL":
        sub.plan_name = "PROFESSIONAL"
        sub.max_users = 25
        sub.max_orders = 2000
        sub.end_date = date.today() + timedelta(days=365)
    elif plan == "ENTERPRISE":
        sub.plan_name = "ENTERPRISE"
        sub.max_users = 100
        sub.max_orders = 10000
        sub.end_date = date.today() + timedelta(days=365)
        
    db.commit()
    db.refresh(sub)
    
    # Write Audit Log
    from app.models.audit_log import AuditLog
    audit = AuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_admin.id,
        action=f"Upgraded subscription plan to {plan}",
        module="Subscription"
    )
    db.add(audit)
    db.commit()
    
    return {"message": f"Successfully upgraded to {plan}", "subscription": sub}
