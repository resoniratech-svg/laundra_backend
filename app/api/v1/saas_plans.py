from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.subscription_plan import SubscriptionPlan

router = APIRouter()

def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SaaS super administrators can access this resource"
        )
    return current_user

class PlanCreatePayload(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = 0.0
    billing_cycle: str = "MONTHLY"
    max_admins: int = 1
    max_cashiers: int = 0
    max_delivery_staff: int = 0
    max_customers: int = 100
    max_orders_per_month: int = 100
    max_storage_mb: int = 1024
    max_api_requests: int = 1000
    is_active: bool = True

class PlanUpdatePayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    billing_cycle: Optional[str] = None
    max_admins: Optional[int] = None
    max_cashiers: Optional[int] = None
    max_delivery_staff: Optional[int] = None
    max_customers: Optional[int] = None
    max_orders_per_month: Optional[int] = None
    max_storage_mb: Optional[int] = None
    max_api_requests: Optional[int] = None
    is_active: Optional[bool] = None

@router.get("", response_model=None)
def list_subscription_plans(
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    return db.query(SubscriptionPlan).all()

@router.post("", status_code=status.HTTP_201_CREATED)
def create_subscription_plan(
    payload: PlanCreatePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    from uuid import uuid4
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plan with this name already exists")
        
    new_plan = SubscriptionPlan(
        id=uuid4(),
        **payload.model_dump()
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    return new_plan

@router.put("/{plan_id}")
def update_subscription_plan(
    plan_id: UUID,
    payload: PlanUpdatePayload,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
        
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
        
    db.commit()
    db.refresh(plan)
    return plan

@router.delete("/{plan_id}")
def delete_subscription_plan(
    plan_id: UUID,
    super_admin: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
        
    db.delete(plan)
    db.commit()
    return {"message": "Subscription plan deleted successfully"}
