from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import func

from app.core.database import get_db
from app.dependencies import get_current_user, get_current_admin, get_current_admin_or_cashier
from app.models.user import User
from app.models.delivery import Delivery
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas.delivery import DeliveryCreate, DeliveryOut
from app.services.delivery_service import DeliveryService
from app.repositories.delivery_repository import DeliveryRepository

router = APIRouter()
delivery_repo = DeliveryRepository()

class DeliveryOTPVerification(BaseModel):
    otp: str
    photos: Optional[str] = None
    notes: Optional[str] = None

class DeliveryOTPVerifyPayload(BaseModel):
    delivery_id: UUID
    otp: str
    photos: Optional[str] = None
    notes: Optional[str] = None

class PickupCompletePayload(BaseModel):
    photos: Optional[str] = None
    notes: Optional[str] = None

@router.post("", response_model=DeliveryOut, status_code=status.HTTP_201_CREATED)
def assign_delivery(
    payload: DeliveryCreate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    return DeliveryService.assign_delivery(
        db,
        order_id=payload.order_id,
        delivery_boy_id=payload.delivery_boy_id,
        courier_name=payload.courier_name,
        delivery_type=payload.type,
        tenant_id=current_admin.tenant_id,
        pickup_commission=payload.pickup_commission,
        delivery_commission=payload.delivery_commission
    )

@router.post("/assign", response_model=DeliveryOut, status_code=status.HTTP_201_CREATED)
def assign_delivery_post(
    payload: DeliveryCreate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    return assign_delivery(payload, current_admin, db)

@router.get("/pickups", response_model=List[DeliveryOut])
def list_pickups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    tenant_id = current_user.tenant_id
    query = db.query(Delivery).filter(
        Delivery.type == "PICKUP",
        Delivery.tenant_id == tenant_id
    )
    if current_user.role == "DELIVERY_BOY":
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Delivery.delivery_boy_id == current_user.id,
                Delivery.delivery_boy_id == None
            )
        )
    return query.all()

@router.get("", response_model=List[DeliveryOut])
def list_deliveries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    from app.models.order import Order
    from sqlalchemy import or_
    from uuid import uuid4
    from decimal import Decimal
    tenant_id = current_user.tenant_id

    if current_user.role == "DELIVERY_BOY":
        # Auto-link any field orders created by this delivery boy
        field_orders = db.query(Order).filter(
            Order.tenant_id == tenant_id,
            or_(
                Order.pickup_staff_id == current_user.id,
                Order.delivery_staff_id == current_user.id,
                Order.special_instructions.ilike(f"%{current_user.name.strip()}%")
            )
        ).all()
        for fo in field_orders:
            has_deliv = db.query(Delivery).filter(
                Delivery.order_id == fo.id,
                Delivery.type == "PICKUP",
                Delivery.tenant_id == tenant_id
            ).first()
            if not has_deliv:
                new_d = Delivery(
                    id=uuid4(),
                    order_id=fo.id,
                    delivery_boy_id=current_user.id,
                    type="PICKUP",
                    status="PICKED",
                    tenant_id=tenant_id,
                    pickup_commission=fo.pickup_commission or Decimal("0.0"),
                    delivery_commission=Decimal("0.0"),
                    pickup_commission_paid=fo.pickup_commission_paid or False,
                    delivery_commission_paid=False,
                    pickup_payment_method=getattr(fo, 'pickup_payment_method', None) or getattr(fo, 'payment_method', None) or "CASH"
                )
                db.add(new_d)
        try:
            db.commit()
        except Exception:
            db.rollback()

        all_delivs = db.query(Delivery).filter(
            or_(
                Delivery.delivery_boy_id == current_user.id,
                Delivery.delivery_boy_id == None
            ),
            Delivery.tenant_id == tenant_id
        ).order_by(Delivery.created_at.desc()).all()
    else:
        all_delivs = db.query(Delivery).filter(Delivery.tenant_id == tenant_id).order_by(Delivery.created_at.desc()).all()
        
    seen = {}
    deduped = []
    for d in all_delivs:
        key = (str(d.order_id), str(d.type))
        if key not in seen:
            seen[key] = d
            deduped.append(d)
        else:
            # Clean up duplicate from DB if it exists
            try:
                db.delete(d)
                db.commit()
            except Exception:
                pass
    return deduped

@router.patch("/{id}/pickup", response_model=DeliveryOut)
def update_pickup_status(
    id: UUID,
    payload: PickupCompletePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    from app.models.order import Order
    from app.models.audit_log import AuditLog
    from app.models.notification import Notification
    from uuid import uuid4
    
    tenant_id = current_user.tenant_id
    
    delivery = db.query(Delivery).filter(
        Delivery.id == id,
        Delivery.tenant_id == tenant_id
    ).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery task not found"
        )
        
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this delivery task as it is not assigned to you."
        )
    
    delivery.status = "PICKED"
    delivery.photos = payload.photos
    delivery.notes = payload.notes
    
    order = db.query(Order).filter(
        Order.id == delivery.order_id,
        Order.tenant_id == tenant_id
    ).first()
    if order:
        order.status = "PICKED_UP"
        
        # 1. Customer Notification
        notif = Notification(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=order.customer_id,
            title="laundry Picked Up",
            message=f"Your order {order.order_number} has been picked up by the delivery staff and is on the way to the laundry.",
            is_read=False
        )
        db.add(notif)
        
    # 2. Audit Log
    audit_log = AuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_user.id,
        action=f"Delivery staff marked pickup task {id} for order {order.order_number if order else 'N/A'} as completed",
        module="DELIVERIES"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(delivery)
    return delivery

@router.patch("/{id}/deliver", response_model=DeliveryOut)
def update_delivery_status(
    id: UUID,
    payload: DeliveryOTPVerification,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    tenant_id = current_user.tenant_id
    
    delivery = db.query(Delivery).filter(
        Delivery.id == id,
        Delivery.tenant_id == tenant_id
    ).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery task not found"
        )
        
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this delivery task as it is not assigned to you."
        )
        
    return DeliveryService.complete_delivery(
        db,
        delivery_id=id,
        otp=payload.otp,
        photos=payload.photos,
        notes=payload.notes,
        tenant_id=current_user.tenant_id
    )

@router.post("/verify-otp", response_model=DeliveryOut)
def verify_otp(
    payload: DeliveryOTPVerifyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    tenant_id = current_user.tenant_id
    
    delivery = db.query(Delivery).filter(
        Delivery.id == payload.delivery_id,
        Delivery.tenant_id == tenant_id
    ).first()
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery task not found"
        )
        
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to verify OTP for this delivery task as it is not assigned to you."
        )
        
    return DeliveryService.complete_delivery(
        db,
        delivery_id=payload.delivery_id,
        otp=payload.otp,
        photos=payload.photos,
        notes=payload.notes,
        tenant_id=current_user.tenant_id
    )

@router.get("/dashboard")
def get_delivery_boy_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery boys can access this dashboard summary"
        )
        
    from app.models.delivery import Delivery
    from app.models.notification import Notification
    tenant_id = current_user.tenant_id
    
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Today's
    today_pickups = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.tenant_id == tenant_id,
        Delivery.type == "PICKUP",
        Delivery.created_at >= today_start
    ).scalar() or 0
    
    today_deliveries = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.tenant_id == tenant_id,
        Delivery.type == "DELIVERY",
        Delivery.created_at >= today_start
    ).scalar() or 0
    
    from sqlalchemy import or_
    
    # Pending Pickups
    pending_pickups = db.query(func.count(Delivery.id)).filter(
        or_(
            Delivery.delivery_boy_id == current_user.id,
            Delivery.delivery_boy_id == None
        ),
        Delivery.tenant_id == tenant_id,
        Delivery.type == "PICKUP",
        Delivery.status != "PICKED",
        Delivery.status != "DELIVERED"
    ).scalar() or 0
    
    # Pending Deliveries
    pending_deliveries = db.query(func.count(Delivery.id)).filter(
        or_(
            Delivery.delivery_boy_id == current_user.id,
            Delivery.delivery_boy_id == None
        ),
        Delivery.tenant_id == tenant_id,
        Delivery.type == "DELIVERY",
        Delivery.status != "DELIVERED"
    ).scalar() or 0
    
    # Completed
    completed_pickups = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.tenant_id == tenant_id,
        Delivery.type == "PICKUP",
        Delivery.status.in_(["PICKED", "DELIVERED"])
    ).scalar() or 0
    
    completed_deliveries = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.tenant_id == tenant_id,
        Delivery.type == "DELIVERY",
        Delivery.status == "DELIVERED"
    ).scalar() or 0
    
    # Missed tasks (not completed tasks scheduled/created before today)
    missed_tasks = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.tenant_id == tenant_id,
        Delivery.created_at < today_start,
        Delivery.status != "DELIVERED",
        Delivery.status != "PICKED"
    ).scalar() or 0
    
    # Notifications count
    notifs = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).scalar() or 0
    
    # Earnings (Flat rate per delivery + Cash Commission)
    from app.models.payment import Payment
    PAYOUT_RATE = 5.0
    today_completed_deliveries = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.tenant_id == tenant_id,
        Delivery.status == "DELIVERED",
        Delivery.updated_at >= today_start
    ).scalar() or 0
    
    today_comm = db.query(func.sum(Payment.delivery_boy_commission)).filter(
        Payment.delivery_boy_id == current_user.id,
        Payment.created_at >= today_start
    ).scalar() or 0.0

    today_earnings = float((today_completed_deliveries * PAYOUT_RATE) + float(today_comm))
    
    return {
        "today_pickups": today_pickups,
        "today_deliveries": today_deliveries,
        "pending_pickups": pending_pickups,
        "pending_deliveries": pending_deliveries,
        "completed_pickups": completed_pickups,
        "completed_deliveries": completed_deliveries,
        "missed_tasks": missed_tasks,
        "notifications": notifs,
        "today_earnings": today_earnings
    }

@router.get("/announcements")
def get_delivery_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery boys can access this announcements feed"
        )
        
    from app.models.announcement import Announcement
    
    # Get all published announcements
    all_published = db.query(Announcement).filter(
        Announcement.status == "PUBLISHED"
    ).order_by(Announcement.scheduled_at.desc()).all()
    
    # Filter announcements targeted to the user's company (tenant_id) or all companies
    delivery_announcements = []
    user_tenant_str = str(current_user.tenant_id)
    
    for ann in all_published:
        if not ann.target_companies:  # null or empty means all companies
            delivery_announcements.append(ann)
        else:
            targets = [t.strip() for t in ann.target_companies.split(",") if t.strip()]
            if user_tenant_str in targets:
                delivery_announcements.append(ann)
                
    return delivery_announcements

class StatusUpdatePayload(BaseModel):
    status: str  # ON_THE_WAY, REACHED, OUT_FOR_DELIVERY, REACHED_CUSTOMER

@router.patch("/{id}/status", response_model=DeliveryOut)
def update_delivery_boy_task_status(
    id: str,
    payload: StatusUpdatePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.audit_log import AuditLog
    from app.models.notification import Notification
    from sqlalchemy import or_
    from uuid import uuid4
    
    tenant_id = current_user.tenant_id
    delivery = None
    try:
        val_uuid = UUID(id)
        delivery = db.query(Delivery).filter(
            or_(Delivery.id == val_uuid, Delivery.order_id == val_uuid),
            Delivery.tenant_id == tenant_id
        ).first()
    except Exception:
        clean_num = str(id).replace('#', '').strip()
        order_obj = db.query(Order).filter(Order.order_number == clean_num, Order.tenant_id == tenant_id).first()
        if order_obj:
            delivery = db.query(Delivery).filter(Delivery.order_id == order_obj.id, Delivery.tenant_id == tenant_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery task not found")
         
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
         
    allowed_statuses = ["ON_THE_WAY", "REACHED", "OUT_FOR_DELIVERY", "REACHED_CUSTOMER", "ACCEPTED", "ASSIGNED", "PICKED", "DELIVERED", "PARTIALLY_PICKED_UP", "PARTIALLY_DELIVERED"]
    if payload.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {allowed_statuses}")
         
    if current_user.role == "DELIVERY_BOY" and not delivery.delivery_boy_id:
        delivery.delivery_boy_id = current_user.id

    delivery.status = payload.status
    
    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    if order:
        if payload.status == "OUT_FOR_DELIVERY":
            order.status = "OUT_FOR_DELIVERY"
        elif payload.status == "DELIVERED":
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

            import json
            from app.models.service import Service
            del_items_log = []
            for item in all_items:
                srv = db.query(Service).filter(Service.id == item.service_id).first()
                if item.delivered_quantity and item.delivered_quantity > 0:
                    del_items_log.append({
                        "service_name": srv.name if srv else "Item",
                        "quantity": item.delivered_quantity
                    })

            if del_items_log:
                existing_del_hist = []
                if order.delivery_history:
                    try:
                        existing_del_hist = json.loads(order.delivery_history) if isinstance(order.delivery_history, str) else order.delivery_history
                    except Exception:
                        existing_del_hist = []

                existing_del_hist.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                    "staff_name": current_user.name if (hasattr(current_user, 'name') and current_user.name) else "Delivery Staff",
                    "items": del_items_log
                })
                order.delivery_history = json.dumps(existing_del_hist)

            if all_fully_delivered:
                order.status = "DELIVERED"
                order.delivery_status = "Delivered"
                order.payment_status = "Paid"
            else:
                order.status = "PARTIALLY DELIVERED"
                order.delivery_status = "Partially Delivered"
            
        title = f"laundry {payload.status.replace('_', ' ').title()}"
        msg = f"Your order {order.order_number} delivery status has been updated to: {payload.status.replace('_', ' ').lower()}"
         
        notif = Notification(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=order.customer_id,
            title=title,
            message=msg,
            is_read=False
        )
        db.add(notif)
         
    audit_log = AuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_user.id,
        action=f"Delivery task {id} status updated to {payload.status}",
        module="DELIVERIES"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(delivery)
    return delivery

@router.get("/{id}/customer-portal-info")
def get_customer_portal_info(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    from app.models.order import Order
    from app.models.customer import Customer
    from app.core.security import create_access_token
    import uuid
    
    tenant_id = current_user.tenant_id
    delivery = db.query(Delivery).filter(
        Delivery.id == id,
        Delivery.tenant_id == tenant_id
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery task not found")
         
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
         
    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first() if order else None
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
         
    if not customer.qr_secret:
        customer.qr_secret = uuid.uuid4().hex
        db.commit()
        
    token = create_access_token(
        subject=f"{customer.id}:{customer.qr_secret}", 
        role="CUSTOMER", 
        tenant_id=str(customer.tenant_id)
    )
    portal_url = f"https://portal.laundry.com/login?token={token}"
    
    return {
        "customer_name": customer.name,
        "customer_phone": customer.phone,
        "portal_url": portal_url,
        "notice": "Customer uses a browser-based QR Customer Portal instead of an APK. You can share this link to help them log in."
    }

@router.get("/{id}/details")
def get_delivery_task_details(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    from app.models.order import Order
    from app.models.customer import Customer
    from app.models.order_item import OrderItem
    from app.models.service import Service
    
    tenant_id = current_user.tenant_id
    delivery = db.query(Delivery).filter(
        Delivery.id == id,
        Delivery.tenant_id == tenant_id
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery task not found")
        
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first() if order else None
    
    # Get order items
    items = []
    if order:
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for oi in order_items:
            srv = db.query(Service).filter(Service.id == oi.service_id).first()
            ord_qty = oi.ordered_quantity if oi.ordered_quantity is not None else (oi.quantity or 1)
            picked_qty = oi.picked_up_quantity or 0
            pending_pickup_qty = oi.pickup_pending_quantity if oi.pickup_pending_quantity is not None else max(0, ord_qty - picked_qty)
            ready_qty = oi.ready_quantity or 0
            del_qty = oi.delivered_quantity or 0
            del_pending_qty = oi.delivery_pending_quantity if oi.delivery_pending_quantity is not None else max(0, ready_qty - del_qty)

            u_price = float(oi.price) if oi.price is not None else 0.0
            q_val = oi.quantity if oi.quantity is not None else ord_qty
            tot_price = float(q_val * u_price)

            items.append({
                "id": str(oi.id),
                "order_item_id": str(oi.id),
                "service_id": str(oi.service_id),
                "service_name": srv.name if srv else "Unknown Service",
                "quantity": ord_qty,
                "ordered_quantity": ord_qty,
                "picked_up_quantity": picked_qty,
                "pickup_pending_quantity": pending_pickup_qty,
                "ready_quantity": ready_qty,
                "delivered_quantity": del_qty,
                "delivery_pending_quantity": del_pending_qty,
                "unit_price": u_price,
                "total_price": tot_price
            })
            
    return {
        "delivery_id": delivery.id,
        "delivery_type": delivery.type,
        "delivery_status": delivery.status,
        "delivery_otp": delivery.otp,
        "delivered_at": delivery.delivered_at,
        "photos": delivery.photos,
        "notes": delivery.notes,
        "pickup_commission": float(delivery.pickup_commission) if delivery.pickup_commission is not None else 0.0,
        "delivery_commission": float(delivery.delivery_commission) if delivery.delivery_commission is not None else 0.0,
        "pickup_commission_paid": bool(delivery.pickup_commission_paid or (order and order.pickup_commission_paid)),
        "delivery_commission_paid": bool(delivery.delivery_commission_paid or (order and order.delivery_commission_paid)),
        "pickup_payment_method": delivery.pickup_payment_method or (order and order.pickup_payment_method),
        "delivery_payment_method": delivery.delivery_payment_method or (order and order.delivery_payment_method),
        "order": {
            "id": order.id if order else None,
            "order_number": order.order_number if order else "N/A",
            "status": order.status if order else "N/A",
            "total_amount": float(order.total_amount) if order and order.total_amount else 0.0,
            "payment_status": order.payment_status if order else "UNPAID",
            "payment_method": getattr(order, 'payment_method', None) or getattr(order, 'pickup_payment_method', None) or getattr(delivery, 'pickup_payment_method', None) or "CASH",
            "pickup_commission": float(order.pickup_commission) if order and order.pickup_commission is not None else float(delivery.pickup_commission or 0.0),
            "delivery_commission": float(order.delivery_commission) if order and order.delivery_commission is not None else float(delivery.delivery_commission or 0.0),
            "pickup_commission_paid": bool(order.pickup_commission_paid or delivery.pickup_commission_paid) if order else bool(delivery.pickup_commission_paid),
            "delivery_commission_paid": bool(order.delivery_commission_paid or delivery.delivery_commission_paid) if order else bool(delivery.delivery_commission_paid),
            "pickup_payment_method": getattr(order, 'pickup_payment_method', None) or getattr(order, 'payment_method', None) or getattr(delivery, 'pickup_payment_method', None) or "CASH",
            "handover_settled": bool(getattr(order, 'handover_settled', False)),
            "handover_settled_at": getattr(order, 'handover_settled_at', None),
            "handover_settled_by": getattr(order, 'handover_settled_by', None),
            "handover_settlement_id": getattr(order, 'handover_settlement_id', None),
            "pickup_address": order.pickup_address if order else "N/A",
            "delivery_address": order.delivery_address if order else "N/A",
            "pickup_date": order.pickup_date if order else None,
            "estimated_delivery_date": order.estimated_delivery_date if order else None,
            "special_instructions": order.special_instructions if order else "",
            "items": items
        },
        "customer": {
            "id": customer.id if customer else None,
            "name": customer.name if customer else "N/A",
            "phone": customer.phone if customer else "N/A",
            "email": customer.email if customer else "N/A"
        }
    }

@router.post("/{id}/accept", response_model=DeliveryOut)
def accept_delivery_task(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    from app.models.audit_log import AuditLog
    from uuid import uuid4
    
    if current_user.role != "DELIVERY_BOY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only delivery boys can accept delivery tasks"
        )
        
    tenant_id = current_user.tenant_id
    delivery = db.query(Delivery).filter(
        Delivery.id == id,
        Delivery.tenant_id == tenant_id
    ).first()
    
    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery task not found"
        )
        
    if delivery.delivery_boy_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This task has already been accepted by another delivery boy"
        )
        
    delivery.delivery_boy_id = current_user.id
    delivery.status = "ACCEPTED"
    
    audit_log = AuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_user.id,
        action=f"Delivery boy {current_user.email} accepted task {id}",
        module="DELIVERIES"
    )
    db.add(audit_log)
    db.commit()
    db.refresh(delivery)
    return delivery


class MarkCommissionPaidRequest(BaseModel):
    staff_id: Optional[str] = None
    staff_name: Optional[str] = None
    delivery_ids: Optional[List[str]] = []
    order_ids: Optional[List[str]] = []
    payment_method: Optional[str] = "Cash"

@router.post("/mark-commission-paid")
def mark_commission_paid(
    payload: MarkCommissionPaidRequest,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    from app.models.order import Order
    from app.models.audit_log import AuditLog
    from app.models.user import User
    from sqlalchemy import or_
    from uuid import uuid4

    tenant_id = current_admin.tenant_id
    updated_count = 0

    if payload.delivery_ids:
        for d_id in payload.delivery_ids:
            clean_did = str(d_id).replace('#', '').strip()
            deliv_uuid = None
            try:
                deliv_uuid = UUID(clean_did)
            except Exception:
                pass
            
            d_query = db.query(Delivery).filter(Delivery.tenant_id == tenant_id)
            if deliv_uuid:
                deliveries = d_query.filter(Delivery.id == deliv_uuid).all()
            else:
                deliveries = d_query.filter(Delivery.order_id == clean_did).all()

            for d in deliveries:
                d.pickup_commission_paid = True
                d.delivery_commission_paid = True
                d.pickup_payment_method = payload.payment_method
                d.delivery_payment_method = payload.payment_method
                updated_count += 1
                if d.order_id:
                    ord_obj = db.query(Order).filter(Order.id == d.order_id, Order.tenant_id == tenant_id).first()
                    if ord_obj:
                        ord_obj.pickup_commission_paid = True
                        ord_obj.delivery_commission_paid = True
                        ord_obj.pickup_payment_method = payload.payment_method
                        ord_obj.delivery_payment_method = payload.payment_method

    if payload.order_ids:
        for o_id in payload.order_ids:
            clean_oid = str(o_id).replace('#', '').strip()
            o_uuid = None
            try:
                o_uuid = UUID(clean_oid)
            except Exception:
                pass

            if o_uuid:
                orders = db.query(Order).filter(
                    or_(Order.id == o_uuid, Order.order_number == clean_oid),
                    Order.tenant_id == tenant_id
                ).all()
            else:
                orders = db.query(Order).filter(
                    Order.order_number == clean_oid,
                    Order.tenant_id == tenant_id
                ).all()

            for o in orders:
                o.pickup_commission_paid = True
                o.delivery_commission_paid = True
                o.pickup_payment_method = payload.payment_method
                o.delivery_payment_method = payload.payment_method
                updated_count += 1

                delivs = db.query(Delivery).filter(Delivery.order_id == o.id, Delivery.tenant_id == tenant_id).all()
                for d in delivs:
                    d.pickup_commission_paid = True
                    d.delivery_commission_paid = True
                    d.pickup_payment_method = payload.payment_method
                    d.delivery_payment_method = payload.payment_method

    elif payload.staff_id or payload.staff_name:
        s_uuid = None
        if payload.staff_id:
            try:
                s_uuid = UUID(str(payload.staff_id))
            except Exception:
                pass
        
        staff_user = db.query(User).filter(User.id == s_uuid, User.tenant_id == tenant_id).first() if s_uuid else None
        if not staff_user and payload.staff_name:
            staff_user = db.query(User).filter(User.name.ilike(payload.staff_name.strip()), User.tenant_id == tenant_id).first()
        
        if staff_user:
            staff_delivs = db.query(Delivery).filter(
                Delivery.delivery_boy_id == staff_user.id,
                Delivery.tenant_id == tenant_id
            ).all()
            for d in staff_delivs:
                if d.type == "PICKUP" and not d.pickup_commission_paid:
                    d.pickup_commission_paid = True
                    d.pickup_payment_method = payload.payment_method
                    updated_count += 1
                elif d.type == "DELIVERY" and not d.delivery_commission_paid:
                    d.delivery_commission_paid = True
                    d.delivery_payment_method = payload.payment_method
                    updated_count += 1
                
                if d.order_id:
                    ord_obj = db.query(Order).filter(Order.id == d.order_id, Order.tenant_id == tenant_id).first()
                    if ord_obj:
                        if d.type == "PICKUP" and not ord_obj.pickup_commission_paid:
                            ord_obj.pickup_commission_paid = True
                            ord_obj.pickup_payment_method = payload.payment_method
                        elif d.type == "DELIVERY" and not ord_obj.delivery_commission_paid:
                            ord_obj.delivery_commission_paid = True
                            ord_obj.delivery_payment_method = payload.payment_method

    audit_log = AuditLog(
        id=uuid4(),
        tenant_id=tenant_id,
        user_id=current_admin.id,
        action=f"Marked commission as paid via {payload.payment_method} for staff {payload.staff_name or payload.staff_id}",
        module="DELIVERIES"
    )
    db.add(audit_log)
    db.commit()

    return {
        "success": True,
        "message": f"Successfully marked commission as paid for {updated_count} items via {payload.payment_method}",
        "updated_count": updated_count
    }

class DriverSettlementCreate(BaseModel):
    settlement_number: Optional[str] = None
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    settled_at: Optional[str] = None
    cash_amount: Optional[Decimal] = Decimal('0.0')
    card_amount: Optional[Decimal] = Decimal('0.0')
    cheque_amount: Optional[Decimal] = Decimal('0.0')
    total_amount: Optional[Decimal] = Decimal('0.0')
    order_count: Optional[int] = 0
    orders: Optional[Any] = None
    notes: Optional[str] = None

@router.get("/settlements")
def list_driver_settlements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.driver_settlement import DriverSettlement
    from datetime import datetime
    tenant_id = current_user.tenant_id

    query = db.query(DriverSettlement).filter(DriverSettlement.tenant_id == tenant_id)
    if current_user.role == "DELIVERY_BOY":
        from sqlalchemy import or_
        query = query.filter(
            or_(
                DriverSettlement.driver_id == current_user.id,
                DriverSettlement.driver_name.ilike(f"%{current_user.name.strip()}%")
            )
        )
    settlements = query.order_by(DriverSettlement.settled_at.desc()).all()
    
    return [
        {
            "id": str(s.id),
            "settlementNumber": s.settlement_number or f"ST-{str(s.id)[:6]}",
            "driverId": str(s.driver_id) if s.driver_id else "",
            "driverName": s.driver_name or "Driver",
            "settledBy": s.settled_by or "Store Admin",
            "settledAt": (s.settled_at.strftime('%Y-%m-%dT%H:%M:%SZ') if s.settled_at else datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')),
            "cashAmount": float(s.cash_amount or 0.0),
            "cardAmount": float(s.card_amount or 0.0),
            "chequeAmount": float(s.cheque_amount or 0.0),
            "onlineAmount": 0.0,
            "totalAmount": float(s.total_amount or 0.0),
            "orderCount": s.order_count or 0,
            "orders": s.orders or [],
            "notes": s.notes or "",
            "status": s.status or "SETTLED"
        }
        for s in settlements
    ]

@router.post("/settlements")
def create_driver_settlement(
    payload: DriverSettlementCreate,
    current_user: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    from app.models.driver_settlement import DriverSettlement
    from app.models.order import Order
    from datetime import datetime
    from uuid import uuid4, UUID
    import random
    tenant_id = current_user.tenant_id

    s_id = uuid4()
    settle_num = payload.settlement_number or f"#ST-{random.randint(100000, 999999)}"
    driver_uuid = None
    if payload.driver_id:
        try:
            driver_uuid = UUID(str(payload.driver_id))
        except Exception:
            pass

    now = datetime.utcnow()
    if payload.settled_at:
        try:
            clean_ts = payload.settled_at.replace('Z', '+00:00')
            now = datetime.fromisoformat(clean_ts)
        except Exception:
            pass

    if not tenant_id and payload.driver_name:
        d_usr = db.query(User).filter(User.name.ilike(f"%{payload.driver_name.strip()}%")).first()
        if d_usr and d_usr.tenant_id:
            tenant_id = d_usr.tenant_id

    new_settlement = DriverSettlement(
        id=s_id,
        tenant_id=tenant_id,
        settlement_number=settle_num,
        driver_id=driver_uuid,
        driver_name=payload.driver_name or "Driver",
        settled_by=current_user.name or "Store Admin",
        settled_at=now,
        cash_amount=payload.cash_amount or Decimal('0.0'),
        card_amount=payload.card_amount or Decimal('0.0'),
        cheque_amount=payload.cheque_amount or Decimal('0.0'),
        total_amount=payload.total_amount or Decimal('0.0'),
        order_count=payload.order_count or (len(payload.orders) if isinstance(payload.orders, list) else 0),
        orders=payload.orders,
        notes=payload.notes,
        status="SETTLED"
    )
    db.add(new_settlement)

    # Mark all associated orders as handover settled
    if isinstance(payload.orders, list):
        for o_item in payload.orders:
            o_id_str = str(o_item.get("orderId") or o_item.get("id") or "")
            if not o_id_str:
                continue
            
            ord_obj = None
            try:
                ord_uuid = UUID(o_id_str)
                ord_obj = db.query(Order).filter(Order.id == ord_uuid).first()
            except Exception:
                pass
            
            if not ord_obj:
                ord_obj = db.query(Order).filter(Order.order_number == o_id_str).first()

            if ord_obj:
                if not new_settlement.tenant_id and ord_obj.tenant_id:
                    new_settlement.tenant_id = ord_obj.tenant_id
                ord_obj.handover_settled = True
                ord_obj.handover_settled_at = now
                ord_obj.handover_settled_by = current_user.name or "Store Admin"
                ord_obj.handover_settlement_id = settle_num

    db.commit()
    db.refresh(new_settlement)

    return {
        "success": True,
        "message": f"Successfully created settlement voucher {settle_num}",
        "settlement": {
            "id": str(new_settlement.id),
            "settlementNumber": new_settlement.settlement_number,
            "driverName": new_settlement.driver_name,
            "settledBy": new_settlement.settled_by,
            "settledAt": new_settlement.settled_at.isoformat() if new_settlement.settled_at else now.isoformat(),
            "cashAmount": float(new_settlement.cash_amount or 0.0),
            "cardAmount": float(new_settlement.card_amount or 0.0),
            "chequeAmount": float(new_settlement.cheque_amount or 0.0),
            "totalAmount": float(new_settlement.total_amount or 0.0),
            "orderCount": new_settlement.order_count or 0,
            "orders": new_settlement.orders or [],
            "status": "SETTLED"
        }
    }


