from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.dependencies import get_current_user, get_current_admin, get_current_admin_or_cashier, check_subscription_active
from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.order import OrderCreate, OrderOut, OrderItemOut, OrderReviewPayload, ReviewReplyPayload, ReviewVisibilityPayload
from app.services.order_service import OrderService
from app.repositories.order_repository import OrderRepository

router = APIRouter()
order_repo = OrderRepository()

class OrderStatusUpdate(BaseModel):
    status: str  # CREATED, RECEIVED, WASHING, IRONING, READY, OUT_FOR_DELIVERY, DELIVERED, CANCELLED

@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: OrderCreate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db),
    _sub: bool = Depends(check_subscription_active)
):
    return OrderService.create_order(
        db,
        customer_id=order_in.customer_id,
        items_in=order_in.items,
        coupon_code=order_in.coupon_code,
        tenant_id=current_admin.tenant_id
    )

@router.get("", response_model=List[OrderOut])
def list_orders(
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    # Retrieve orders with automatic tenant filter applied in order_repo
    orders = order_repo.get_multi(db, tenant_id=current_admin.tenant_id)
    # Populate items for each order
    for o in orders:
        o.items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
    return orders

@router.get("/{id}", response_model=OrderOut)
def get_order(
    id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return order

@router.patch("/{id}/status", response_model=OrderOut)
def update_order_status(
    id: UUID,
    payload: OrderStatusUpdate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    order.status = payload.status
    
    if payload.status == "READY":
        # Check if DELIVERY task already exists
        from app.models.delivery import Delivery
        from uuid import uuid4
        from datetime import datetime
        
        existing_deliv = db.query(Delivery).filter(
            Delivery.order_id == id,
            Delivery.type == "DELIVERY"
        ).first()
        if not existing_deliv:
            import random
            delivery_otp = "".join([str(random.randint(0,9)) for _ in range(4)])
            new_deliv = Delivery(
                id=uuid4(),
                tenant_id=current_admin.tenant_id,
                order_id=id,
                delivery_boy_id=None,  # Unassigned open pool
                type="DELIVERY",
                status="PENDING",
                otp=delivery_otp,
                created_at=datetime.utcnow()
            )
            db.add(new_deliv)
            
            # Notify customer with the delivery OTP
            from app.models.notification import Notification
            from app.models.customer import Customer
            notif = Notification(
                id=uuid4(),
                tenant_id=current_admin.tenant_id,
                user_id=order.customer_id,
                title="Your Delivery OTP",
                message=f"Your laundry order {order.order_number} is ready! Your delivery verification OTP is: {delivery_otp}. Share this with the delivery person upon receiving your order.",
                is_read=False
            )
            db.add(notif)
            
            # Also send OTP via email
            customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
            if customer and customer.email:
                try:
                    from app.core.email_service import send_otp_email
                    send_otp_email(db, customer.email, delivery_otp)
                except Exception:
                    pass  # Don't block order status update if email fails

    db.commit()
    db.refresh(order)
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return order

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    discount: Optional[Decimal] = None
    paid_amount: Optional[Decimal] = None
    payment_status: Optional[str] = None

@router.put("/{id}", response_model=OrderOut)
def update_order(
    id: UUID,
    payload: OrderUpdate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    update_data = payload.model_dump(exclude_unset=True)
    updated_order = order_repo.update(db, db_obj=order, obj_in=update_data)
    updated_order.items = db.query(OrderItem).filter(OrderItem.order_id == updated_order.id).all()
    return updated_order

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def cancel_order(
    id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    order.status = "CANCELLED"
    db.commit()
    return {"success": True, "message": "Order cancelled successfully"}

@router.post("/{id}/review", response_model=OrderOut)
def review_order(
    id: UUID,
    payload: OrderReviewPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
      
    if current_user.role == "CUSTOMER" and order.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only rate your own orders."
        )
          
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be between 1 and 5."
        )
          
    order.rating = payload.rating
    order.review = payload.review
    db.commit()
    db.refresh(order)
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return order

@router.get("/reviews", response_model=List[OrderOut])
def list_company_reviews(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    from app.core.tenant import get_current_tenant_id
    tenant_id = get_current_tenant_id()
    
    # Return all rated orders belonging to the tenant
    reviews = db.query(Order).filter(
        Order.tenant_id == tenant_id,
        Order.rating != None
    ).order_by(Order.updated_at.desc()).all()
    
    for r in reviews:
        r.items = db.query(OrderItem).filter(OrderItem.order_id == r.id).all()
        
    return reviews

@router.post("/{id}/reviews/reply", response_model=OrderOut)
def reply_to_review(
    id: UUID,
    payload: ReviewReplyPayload,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
        
    order.review_reply = payload.reply
    db.commit()
    db.refresh(order)
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return order

@router.patch("/{id}/reviews/visibility", response_model=OrderOut)
def toggle_review_visibility(
    id: UUID,
    payload: ReviewVisibilityPayload,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
        
    order.review_hidden = payload.is_hidden
    db.commit()
    db.refresh(order)
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return order


