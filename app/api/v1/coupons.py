from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import uuid4, UUID
from decimal import Decimal
from pydantic import BaseModel
from datetime import date

from app.core.database import get_db
from app.dependencies import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.coupon import CouponCreate, CouponOut
from app.repositories.coupon_repository import CouponRepository

router = APIRouter()
coupon_repo = CouponRepository()

class ApplyCouponPayload(BaseModel):
    code: str
    customer_id: UUID
    amount: Decimal

@router.post("", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
def create_coupon(
    coupon_in: CouponCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    obj_data = coupon_in.model_dump()
    obj_data["id"] = uuid4()
    obj_data["tenant_id"] = current_admin.tenant_id
    
    return coupon_repo.create(db, obj_in=obj_data)

@router.get("/public", response_model=List[CouponOut])
def list_public_coupons(
    tenant_id: UUID,
    db: Session = Depends(get_db)
):
    return coupon_repo.get_active_multi(db, tenant_id=tenant_id)

@router.get("", response_model=List[CouponOut])
def list_coupons(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return coupon_repo.get_multi(db, tenant_id=current_user.tenant_id)

@router.post("/apply")
def apply_coupon(
    payload: ApplyCouponPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.coupon import Coupon
    tenant_id = current_user.tenant_id
    
    coupon = db.query(Coupon).filter(
        Coupon.code == payload.code,
        Coupon.tenant_id == tenant_id
    ).first()
    
    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid coupon code"
        )
        
    if coupon.expiry_date and coupon.expiry_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coupon has expired"
        )
        
    discount = Decimal("0.0")
    if coupon.discount_type == "PERCENTAGE":
        discount = payload.amount * (coupon.value / Decimal("100.0"))
    elif coupon.discount_type == "FLAT":
        discount = coupon.value
        
    discount = min(discount, payload.amount)
    return {
        "success": True,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "value": coupon.value,
        "discount_applied": discount
    }

@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(
    coupon_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    coupon = coupon_repo.get(db, coupon_id)
    if not coupon or coupon.tenant_id != current_admin.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found"
        )
    coupon_repo.remove(db, id=coupon_id)
    return None
