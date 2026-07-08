from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import func

from app.core.database import get_db
from app.dependencies import get_current_user, get_current_admin, get_current_admin_or_cashier
from app.models.user import User
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
        delivery_type=payload.type,
        tenant_id=current_admin.tenant_id
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
    if current_user.role == "DELIVERY_BOY":
        from app.models.delivery import Delivery
        from sqlalchemy import or_
        tenant_id = current_user.tenant_id
        return db.query(Delivery).filter(
            or_(
                Delivery.delivery_boy_id == current_user.id,
                Delivery.delivery_boy_id == None
            ),
            Delivery.tenant_id == tenant_id
        ).all()
        
    return delivery_repo.get_multi(db)

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
    
    # Pending
    pending_pickups = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
        Delivery.tenant_id == tenant_id,
        Delivery.type == "PICKUP",
        Delivery.status != "PICKED",
        Delivery.status != "DELIVERED"
    ).scalar() or 0
    
    pending_deliveries = db.query(func.count(Delivery.id)).filter(
        Delivery.delivery_boy_id == current_user.id,
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
    id: UUID,
    payload: StatusUpdatePayload,
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
        raise HTTPException(status_code=404, detail="Delivery task not found")
         
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
         
    allowed_statuses = ["ON_THE_WAY", "REACHED", "OUT_FOR_DELIVERY", "REACHED_CUSTOMER"]
    if payload.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {allowed_statuses}")
         
    delivery.status = payload.status
    
    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    if order:
        if payload.status == "OUT_FOR_DELIVERY":
            order.status = "OUT_FOR_DELIVERY"
            
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
        
    if current_user.role == "DELIVERY_BOY" and delivery.delivery_boy_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first() if order else None
    
    # Get order items
    items = []
    if order:
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for oi in order_items:
            srv = db.query(Service).filter(Service.id == oi.service_id).first()
            items.append({
                "service_id": oi.service_id,
                "service_name": srv.name if srv else "Unknown Service",
                "quantity": oi.quantity,
                "unit_price": float(oi.price),
                "total_price": float(oi.quantity * oi.price)
            })
            
    return {
        "delivery_id": delivery.id,
        "delivery_type": delivery.type,
        "delivery_status": delivery.status,
        "delivery_otp": delivery.otp,
        "delivered_at": delivery.delivered_at,
        "photos": delivery.photos,
        "notes": delivery.notes,
        "order": {
            "id": order.id if order else None,
            "order_number": order.order_number if order else "N/A",
            "status": order.status if order else "N/A",
            "total_amount": order.total_amount if order else 0.0,
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


