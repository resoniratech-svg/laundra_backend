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

# Store OTPs temporarily (In a real app, use Redis)
# Format: { "order_id_action": "otp_code" }
MOCK_ORDER_OTP_STORE = {}

class OrderStatusUpdate(BaseModel):
    status: str  # CREATED, RECEIVED, WASHING, IRONING, READY, OUT_FOR_DELIVERY, DELIVERED, CANCELLED

@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: OrderCreate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db),
    _sub: bool = Depends(check_subscription_active)
):
    # Enforce subscription monthly orders limit
    from app.core.subscription_limits import check_monthly_orders_limit
    check_monthly_orders_limit(db, current_admin.tenant_id)

    from app.models.customer_package import CustomerPackage
    order = OrderService.create_order(
        db,
        customer_id=order_in.customer_id,
        items_in=order_in.items,
        coupon_code=order_in.coupon_code,
        tenant_id=current_admin.tenant_id,
        is_express=order_in.is_express,
        pay_with_package_id=order_in.pay_with_package_id,
        pickup_address=order_in.pickup_address,
        delivery_address=order_in.delivery_address,
        special_instructions=order_in.special_instructions,
        pickup_date=order_in.pickup_date
    )
    if order.applied_package_id:
        cp = db.query(CustomerPackage).filter(CustomerPackage.id == order.applied_package_id).first()
        if cp and cp.package:
            setattr(order, 'package_name', cp.package.name)
    return order

@router.get("", response_model=List[OrderOut])
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["ADMIN", "CASHIER", "SUPER_ADMIN", "CUSTOMER", "DELIVERY_BOY"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges."
        )
    from app.models.customer_package import CustomerPackage
    from app.models.service import Service
    orders = order_repo.get_multi(db, tenant_id=current_user.tenant_id)
    for o in orders:
        o.items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        for item in o.items:
            svc = db.query(Service).filter(Service.id == item.service_id).first()
            if svc:
                setattr(item, 'service_name', svc.name)
        if o.applied_package_id:
            cp = db.query(CustomerPackage).filter(CustomerPackage.id == o.applied_package_id).first()
            if cp and cp.package:
                setattr(o, 'package_name', cp.package.name)
    return orders

@router.get("/{id}", response_model=OrderOut)
def get_order(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["ADMIN", "CASHIER", "SUPER_ADMIN", "CUSTOMER", "DELIVERY_BOY"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges."
        )
    from app.models.customer_package import CustomerPackage
    from app.models.service import Service
    
    order = None
    try:
        from uuid import UUID as PyUUID
        val_uuid = PyUUID(id)
        order = db.query(Order).filter(Order.id == val_uuid, Order.tenant_id == current_user.tenant_id).first()
    except Exception:
        clean_num = str(id).replace('#', '').strip()
        order = db.query(Order).filter(Order.order_number == clean_num, Order.tenant_id == current_user.tenant_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    for item in order.items:
        svc = db.query(Service).filter(Service.id == item.service_id).first()
        if svc:
            setattr(item, 'service_name', svc.name)
    if order.applied_package_id:
        cp = db.query(CustomerPackage).filter(CustomerPackage.id == order.applied_package_id).first()
        if cp and cp.package:
            setattr(order, 'package_name', cp.package.name)
    return order

@router.patch("/{id}/status", response_model=OrderOut)
def update_order_status(
    id: UUID,
    payload: OrderStatusUpdate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id, tenant_id=current_admin.tenant_id)
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
    order = order_repo.get(db, id, tenant_id=current_admin.tenant_id)
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
def delete_order(
    id: str,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    # Try finding order by UUID first, then fallback to order_number
    order = None
    try:
        uuid_val = UUID(id)
        order = order_repo.get(db, uuid_val, tenant_id=current_admin.tenant_id)
    except (ValueError, TypeError):
        pass

    if not order:
        order = db.query(Order).filter(Order.order_number == id, Order.tenant_id == current_admin.tenant_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    # Hard delete: remove order items first, then the order itself
    db.query(OrderItem).filter(OrderItem.order_id == order.id).delete()
    db.delete(order)
    db.commit()
    return {"success": True, "message": "Order permanently deleted"}

class OrderOtpSendPayload(BaseModel):
    action: str  # 'pickup' or 'delivery'

class OrderOtpVerifyPayload(BaseModel):
    action: str  # 'pickup' or 'delivery'
    otp: str

@router.post("/{id}/send-otp")
def send_order_otp(
    id: UUID,
    payload: OrderOtpSendPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import random
    from app.core.email_service import send_order_otp_email
    from app.models.company import Company
    
    # We allow DELIVERY_BOY and ADMIN
    order = order_repo.get(db, id)
    if not order or order.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
        
    customer = order.customer
    if not customer or not customer.email:
        raise HTTPException(status_code=400, detail="Customer has no registered email.")
        
    company = db.query(Company).filter(Company.id == current_user.tenant_id).first()
    company_name = company.name if company else "our Laundry Platform"
    
    otp_code = f"{random.randint(100000, 999999)}"
    store_key = f"{str(id)}_{payload.action}"
    MOCK_ORDER_OTP_STORE[store_key] = otp_code
    
    email_sent = send_order_otp_email(db, customer.email, otp_code, payload.action, company_name)
    if not email_sent:
         raise HTTPException(status_code=500, detail="Failed to send OTP email.")
         
    return {"success": True, "message": f"OTP sent to {customer.email}"}

@router.post("/{id}/verify-otp", response_model=OrderOut)
def verify_order_otp(
    id: UUID,
    payload: OrderOtpVerifyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # We allow DELIVERY_BOY and ADMIN
    order = order_repo.get(db, id)
    if not order or order.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
        
    store_key = f"{str(id)}_{payload.action}"
    if payload.otp and payload.otp != "BYPASS":
        expected_otp = MOCK_ORDER_OTP_STORE.get(store_key)
        if expected_otp and expected_otp != payload.otp:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    if store_key in MOCK_ORDER_OTP_STORE:
        del MOCK_ORDER_OTP_STORE[store_key]
    
    # Update order status based on action
    from app.models.delivery import Delivery
    if payload.action == "pickup":
        order.status = "RECEIVED"
        order.delivery_status = "Pending Delivery"
        deliveries = db.query(Delivery).filter(Delivery.order_id == order.id, Delivery.type == "PICKUP").all()
        for d in deliveries:
            d.status = "PICKED"
    elif payload.action == "delivery":
        all_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for item in all_items:
            rdy = item.ready_quantity or 0
            pck = item.picked_up_quantity if (item.picked_up_quantity is not None and item.picked_up_quantity > 0) else 0
            del_qty = item.delivered_quantity or 0

            max_deliverable = max(0, pck - del_qty)
            del_batch = min(rdy, max_deliverable)
            new_del = min(pck, del_qty + del_batch)

            item.delivered_quantity = new_del
            item.ready_quantity = 0
            item.delivery_pending_quantity = max(0, pck - new_del)

            if new_del >= pck and pck > 0:
                item.item_status = "FULLY_DELIVERED"
            else:
                item.item_status = "PARTIALLY_DELIVERED"

        all_fully_delivered = all(
            (i.delivered_quantity or 0) >= (i.picked_up_quantity if (i.picked_up_quantity is not None and i.picked_up_quantity > 0) else (i.ordered_quantity or i.quantity or 1))
            and (i.delivery_pending_quantity or 0) == 0
            for i in all_items
        )

        if all_fully_delivered:
            order.status = "DELIVERED"
            order.delivery_status = "Delivered"
            order.payment_status = "PAID"
            deliveries = db.query(Delivery).filter(Delivery.order_id == order.id, Delivery.type == "DELIVERY").all()
            for d in deliveries:
                d.status = "DELIVERED"
        else:
            order.status = "PARTIALLY DELIVERED"
            order.delivery_status = "Partially Delivered"

    db.commit()
    db.refresh(order)
    
    # Populate items for response
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return order

@router.post("/{id}/review", response_model=OrderOut)
def review_order(
    id: UUID,
    payload: OrderReviewPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = order_repo.get(db, id, tenant_id=current_user.tenant_id)
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
    order = order_repo.get(db, id, tenant_id=current_admin.tenant_id)
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
    order = order_repo.get(db, id, tenant_id=current_admin.tenant_id)
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

import json
from datetime import datetime

class ItemQuantityAction(BaseModel):
    item_id: UUID
    quantity: int

class PartialActionPayload(BaseModel):
    items: List[ItemQuantityAction]
    staff_name: Optional[str] = None

@router.post("/{id}/pickup-items", response_model=OrderOut)
def pickup_order_items(
    id: str,
    payload: PartialActionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from sqlalchemy import or_
    try:
        from uuid import UUID as PyUUID
        val_uuid = PyUUID(id)
        order = db.query(Order).filter(or_(Order.id == val_uuid, Order.order_number == id)).first()
    except ValueError:
        order = db.query(Order).filter(Order.order_number == id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not payload.items:
        raise HTTPException(status_code=400, detail="No items provided for pickup")

    pickup_logs = []
    staff_name = payload.staff_name or current_user.name or "Delivery Staff"

    for action_item in payload.items:
        if action_item.quantity <= 0:
            continue

        item = None
        raw_id_str = str(action_item.item_id).strip()
        try:
            val_item_uuid = PyUUID(raw_id_str)
            item = db.query(OrderItem).filter(
                or_(OrderItem.id == val_item_uuid, OrderItem.id == raw_id_str),
                OrderItem.order_id == order.id
            ).first()
        except Exception:
            item = db.query(OrderItem).filter(
                OrderItem.id == raw_id_str,
                OrderItem.order_id == order.id
            ).first()

        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"OrderItem with ID '{action_item.item_id}' not found for order '{order.order_number}'"
            )

        ordered_qty = item.ordered_quantity if item.ordered_quantity is not None else item.quantity
        curr_picked = item.picked_up_quantity or 0
        curr_pending = max(0, ordered_qty - curr_picked)

        if action_item.quantity > curr_pending:
            raise HTTPException(
                status_code=400,
                detail=f"Pickup quantity ({action_item.quantity}) cannot exceed pickup pending quantity ({curr_pending}) for item"
            )

        new_picked = curr_picked + action_item.quantity
        item.picked_up_quantity = new_picked
        item.ordered_quantity = ordered_qty
        item.pickup_pending_quantity = max(0, ordered_qty - new_picked)
        item.delivery_pending_quantity = max(0, new_picked - (item.delivered_quantity or 0))

        if new_picked >= ordered_qty:
            item.item_status = "FULLY_PICKED_UP"
        else:
            item.item_status = "PARTIALLY_PICKED_UP"

        from app.models.service import Service
        service = db.query(Service).filter(Service.id == item.service_id).first()
        service_name = service.name if service else "Service"

        pickup_logs.append({
            "item_id": str(item.id),
            "service_name": service_name,
            "quantity": action_item.quantity
        })

    if pickup_logs:
        history_list = []
        if order.pickup_history:
            try:
                history_list = json.loads(order.pickup_history)
            except Exception:
                history_list = []
        
        history_list.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            "staff_name": staff_name,
            "items": pickup_logs
        })
        order.pickup_history = json.dumps(history_list)

    all_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    all_fully_picked = all((i.picked_up_quantity or 0) >= (i.ordered_quantity or i.quantity or 1) for i in all_items)
    any_picked = any((i.picked_up_quantity or 0) > 0 for i in all_items)

    if all_fully_picked:
        order.status = "FULLY PICKED UP"
    elif any_picked:
        order.status = "PARTIALLY PICKED UP"

    db.commit()
    db.refresh(order)
    order.items = all_items
    return order

@router.post("/{id}/deliver-items", response_model=OrderOut)
def deliver_order_items(
    id: str,
    payload: PartialActionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from sqlalchemy import or_
    try:
        from uuid import UUID as PyUUID
        val_uuid = PyUUID(id)
        order = db.query(Order).filter(or_(Order.id == val_uuid, Order.order_number == id)).first()
    except ValueError:
        order = db.query(Order).filter(Order.order_number == id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not payload.items:
        raise HTTPException(status_code=400, detail="No items provided for delivery")

    delivery_logs = []
    staff_name = payload.staff_name or current_user.name or "Delivery Staff"

    for action_item in payload.items:
        if action_item.quantity <= 0:
            continue

        item = None
        raw_id_str = str(action_item.item_id).strip()
        try:
            val_item_uuid = PyUUID(raw_id_str)
            item = db.query(OrderItem).filter(
                or_(OrderItem.id == val_item_uuid, OrderItem.id == raw_id_str),
                OrderItem.order_id == order.id
            ).first()
        except Exception:
            item = db.query(OrderItem).filter(
                OrderItem.id == raw_id_str,
                OrderItem.order_id == order.id
            ).first()

        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"OrderItem with ID '{action_item.item_id}' not found for order '{order.order_number}'"
            )

        ordered_qty = item.ordered_quantity if item.ordered_quantity is not None else item.quantity
        curr_picked = item.picked_up_quantity if (item.picked_up_quantity is not None and item.picked_up_quantity > 0) else ordered_qty
        curr_delivered = item.delivered_quantity or 0
        curr_delivery_pending = max(0, curr_picked - curr_delivered)

        if action_item.quantity > curr_delivery_pending:
            raise HTTPException(
                status_code=400,
                detail=f"Delivered quantity ({action_item.quantity}) cannot exceed delivery pending quantity ({curr_delivery_pending}) for item"
            )

        new_delivered = curr_delivered + action_item.quantity
        item.delivered_quantity = new_delivered
        item.delivery_pending_quantity = max(0, curr_picked - new_delivered)

        if new_delivered >= ordered_qty:
            item.item_status = "FULLY_DELIVERED"
        else:
            item.item_status = "PARTIALLY_DELIVERED"

        from app.models.service import Service
        service = db.query(Service).filter(Service.id == item.service_id).first()
        service_name = service.name if service else "Service"

        delivery_logs.append({
            "item_id": str(item.id),
            "service_name": service_name,
            "quantity": action_item.quantity
        })

    if delivery_logs:
        history_list = []
        if order.delivery_history:
            try:
                history_list = json.loads(order.delivery_history)
            except Exception:
                history_list = []
        
        history_list.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
            "staff_name": staff_name,
            "items": delivery_logs
        })
        order.delivery_history = json.dumps(history_list)

    all_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    all_fully_delivered = all((i.delivered_quantity or 0) >= (i.ordered_quantity or i.quantity or 1) for i in all_items)
    any_delivered = any((i.delivered_quantity or 0) > 0 for i in all_items)
    all_fully_picked = all((i.picked_up_quantity or 0) >= (i.ordered_quantity or i.quantity or 1) for i in all_items)

    if all_fully_delivered:
        order.status = "DELIVERED"
    elif any_delivered:
        order.status = "PARTIALLY DELIVERED"
    elif all_fully_picked:
        order.status = "FULLY PICKED UP"

    db.commit()
    db.refresh(order)
    order.items = all_items
    return order


@router.post("/{id}/ready-items", response_model=OrderOut)
def update_ready_order_items(
    id: str,
    payload: PartialActionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from sqlalchemy import or_
    try:
        from uuid import UUID as PyUUID
        val_uuid = PyUUID(id)
        order = db.query(Order).filter(or_(Order.id == val_uuid, Order.order_number == id)).first()
    except ValueError:
        order = db.query(Order).filter(Order.order_number == id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    for action_item in payload.items:
        item = None
        raw_id_str = str(action_item.item_id).strip()
        try:
            val_item_uuid = PyUUID(raw_id_str)
            item = db.query(OrderItem).filter(
                or_(OrderItem.id == val_item_uuid, OrderItem.id == raw_id_str),
                OrderItem.order_id == order.id
            ).first()
        except Exception:
            item = db.query(OrderItem).filter(
                OrderItem.id == raw_id_str,
                OrderItem.order_id == order.id
            ).first()

        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"OrderItem with ID '{action_item.item_id}' not found for order '{order.order_number}'"
            )

        pck = item.picked_up_quantity or 0
        if action_item.quantity < 0:
            raise HTTPException(status_code=400, detail="Ready quantity cannot be negative")
        if action_item.quantity > pck:
            raise HTTPException(
                status_code=400,
                detail=f"Ready quantity ({action_item.quantity}) cannot exceed Picked Up quantity ({pck})"
            )

        item.ready_quantity = action_item.quantity
        del_qty = item.delivered_quantity or 0
        item.delivery_pending_quantity = max(0, pck - del_qty)

    all_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    db.commit()
    db.refresh(order)
    order.items = all_items
    return order


