from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from uuid import uuid4, UUID
from datetime import datetime, timedelta
import random
from typing import List
from fpdf import FPDF

from app.core.database import get_db
from app.dependencies import get_current_customer
from app.models.customer import Customer
from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.service import Service
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.support_ticket import SupportTicket
from app.models.coupon import Coupon
from app.models.notification import Notification
from app.models.customer_address import CustomerAddress
from app.models.review import Review

from app.schemas.portal import (
    CustomerProfileOut, CustomerProfileUpdate, ChangePasswordPayload,
    CustomerOrderOut, CustomerOrderCreate, OrderTimelineEntry,
    CustomerPaymentOut, CustomerPaymentCreate, WalletPayPayload,
    LoyaltyRedeemPayload, CustomerReviewOut, CustomerReviewCreate,
    CustomerTicketCreate, AddressCreate, AddressUpdate, DashboardOut
)

from app.core.security import get_password_hash, verify_password

router = APIRouter()

# ── 1. DASHBOARD ─────────────────────────────────────────
@router.get("/dashboard", response_model=DashboardOut)
def get_customer_dashboard(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    active_orders = db.query(Order).filter(
        Order.customer_id == current_customer.id,
        Order.status.notin_(["DELIVERED", "CANCELLED"])
    ).count()

    in_progress = db.query(Order).filter(
        Order.customer_id == current_customer.id,
        Order.status.in_(["RECEIVED", "WASHING", "IRONING"])
    ).count()

    ready = db.query(Order).filter(
        Order.customer_id == current_customer.id,
        Order.status == "READY"
    ).count()

    delivered = db.query(Order).filter(
        Order.customer_id == current_customer.id,
        Order.status == "DELIVERED"
    ).count()

    pending_payments = db.query(Order).filter(
        Order.customer_id == current_customer.id,
        Order.payment_status != "PAID",
        Order.status != "CANCELLED"
    ).count()

    unread_notifs = db.query(Notification).filter(
        Notification.user_id == current_customer.id,
        Notification.is_read == False
    ).count()

    return DashboardOut(
        active_orders=active_orders,
        in_progress_orders=in_progress,
        ready_for_delivery=ready,
        delivered_orders=delivered,
        pending_payments=pending_payments,
        wallet_balance=current_customer.wallet_balance,
        loyalty_points=current_customer.loyalty_points,
        unread_notifications=unread_notifs
    )

# ── 2. PROFILE & PASSWORD ────────────────────────────────
@router.get("/profile", response_model=CustomerProfileOut)
def get_customer_profile(current_customer: Customer = Depends(get_current_customer)):
    return current_customer

@router.get("/my-qr")
def get_my_qr(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    import qrcode
    import base64
    from io import BytesIO
    from urllib.parse import quote
    from app.core.security import create_access_token
    import uuid

    if not current_customer.qr_secret:
        current_customer.qr_secret = uuid.uuid4().hex
        db.commit()

    token = create_access_token(
        subject=f"{current_customer.id}:{current_customer.qr_secret}", 
        role="CUSTOMER", 
        tenant_id=str(current_customer.tenant_id)
    )
    portal_url = f"https://portal.laundry.com/login?token={token}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(portal_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    message = f"Hello {current_customer.name}!\n\nAccess your Laundry Portal securely using this link:\n{portal_url}\n\nThank you for choosing us!"
    whatsapp_url = f"https://wa.me/?text={quote(message)}"

    return {
        "portal_url": portal_url,
        "qr_image_base64": f"data:image/png;base64,{img_str}",
        "whatsapp_url": whatsapp_url
    }

@router.put("/profile", response_model=CustomerProfileOut)
def update_customer_profile(
    payload: CustomerProfileUpdate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_customer.id).first()
    
    if payload.name is not None:
        current_customer.name = payload.name
        if user: user.name = payload.name
    if payload.phone is not None:
        current_customer.phone = payload.phone
        if user: user.phone = payload.phone
    if payload.email is not None:
        current_customer.email = payload.email
        if user: user.email = payload.email
    if payload.address is not None:
        current_customer.address = payload.address
    if payload.profile_photo is not None:
        current_customer.profile_photo = payload.profile_photo

    db.commit()
    db.refresh(current_customer)
    return current_customer

@router.put("/profile/password")
def change_customer_password(
    payload: ChangePasswordPayload,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_customer.id).first()
    if not user or not verify_password(payload.current_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    user.password = get_password_hash(payload.new_password)
    db.commit()
    return {"success": True, "message": "Password updated successfully"}

# ── 3. ORDERS ────────────────────────────────────────────
@router.post("/orders", response_model=CustomerOrderOut, status_code=status.HTTP_201_CREATED)
def place_order(
    payload: CustomerOrderCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must have at least one item")
        
    total_amount = 0.0
    order_items = []
    
    for item in payload.items:
        service = db.query(Service).filter(
            Service.id == item.service_id,
            Service.tenant_id == current_customer.tenant_id
        ).first()
        if not service:
            raise HTTPException(status_code=404, detail=f"Service {item.service_id} not found")
        
        # Express pricing calculation
        price = service.express_price if (payload.is_express and service.express_price is not None) else service.price
        item_total = float(price) * item.quantity
        total_amount += item_total
        
        order_items.append(OrderItem(
            id=uuid4(),
            service_id=service.id,
            quantity=item.quantity,
            price=price
        ))

    # Apply Coupon
    discount = 0.0
    if payload.coupon_code:
        coupon = db.query(Coupon).filter(
            Coupon.code == payload.coupon_code,
            Coupon.tenant_id == current_customer.tenant_id
        ).first()
        if coupon:
            if coupon.discount_type == "PERCENTAGE":
                discount = total_amount * (float(coupon.value) / 100.0)
            else:
                discount = float(coupon.value)
            discount = min(discount, total_amount)

    order_id = uuid4()
    order_number = str(random.randint(100000, 999999))
    
    # Calculate estimated delivery (Normal: 3 days, Express: 1 day)
    est_days = 1 if payload.is_express else 3
    estimated_delivery = (payload.pickup_date or datetime.utcnow()) + timedelta(days=est_days)

    new_order = Order(
        id=order_id,
        tenant_id=current_customer.tenant_id,
        customer_id=current_customer.id,
        order_number=order_number,
        status="CREATED",
        total_amount=total_amount - discount,
        discount=discount,
        paid_amount=0.0,
        payment_status="UNPAID",
        pickup_address=payload.pickup_address or current_customer.address,
        delivery_address=payload.delivery_address or current_customer.address,
        pickup_date=payload.pickup_date or datetime.utcnow(),
        estimated_delivery_date=estimated_delivery,
        special_instructions=payload.special_instructions,
        is_express=payload.is_express
    )

    for item in order_items:
        item.order_id = order_id
        db.add(item)
        
    from app.models.delivery import Delivery
    
    pickup_task = Delivery(
        id=uuid4(),
        tenant_id=current_customer.tenant_id,
        order_id=order_id,
        delivery_boy_id=None,  # Unassigned open pool
        type="PICKUP",
        status="PENDING",
        otp="".join([str(random.randint(0,9)) for _ in range(4)]),
        created_at=datetime.utcnow()
    )
    db.add(pickup_task)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order

@router.get("/orders", response_model=List[CustomerOrderOut])
def list_my_orders(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    orders = db.query(Order).filter(Order.customer_id == current_customer.id).order_by(Order.created_at.desc()).all()
    # Populate items for order schemas
    for o in orders:
        o.items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
    return orders

@router.get("/orders/{id}", response_model=CustomerOrderOut)
def get_my_order(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return order

@router.get("/orders/{id}/timeline", response_model=List[OrderTimelineEntry])
def get_order_timeline(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    statuses = ["CREATED", "RECEIVED", "WASHING", "IRONING", "READY", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"]
    current_idx = statuses.index(order.status) if order.status in statuses else 0
    
    timeline = []
    base_time = order.created_at
    
    descriptions = {
        "CREATED": "Order placed successfully",
        "RECEIVED": "Laundry picked up & received at cleaning center",
        "WASHING": "Clothes sorting and washing in progress",
        "IRONING": "Steaming and ironing in progress",
        "READY": "Quality checked, folded and packed",
        "OUT_FOR_DELIVERY": "Out for delivery with delivery executive",
        "DELIVERED": "Successfully delivered to customer",
        "CANCELLED": "Order cancelled"
    }
    
    # If cancelled, show created then cancelled
    if order.status == "CANCELLED":
        timeline.append(OrderTimelineEntry(status="CREATED", timestamp=base_time, description=descriptions["CREATED"]))
        timeline.append(OrderTimelineEntry(status="CANCELLED", timestamp=order.updated_at, description=descriptions["CANCELLED"]))
        return timeline
        
    for i in range(current_idx + 1):
        step_status = statuses[i]
        if step_status == "CANCELLED": continue
        step_time = base_time + timedelta(hours=i*2) if i > 0 else base_time
        if i == current_idx:
            step_time = order.updated_at
        timeline.append(OrderTimelineEntry(
            status=step_status,
            timestamp=step_time,
            description=descriptions.get(step_status, step_status)
        ))
    return timeline

@router.post("/orders/{id}/cancel")
def cancel_my_order(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "CREATED":
        raise HTTPException(status_code=400, detail="Cannot cancel order after it has been received/processed")
    order.status = "CANCELLED"
    db.commit()
    return {"success": True, "message": "Order cancelled successfully"}

@router.post("/orders/{id}/reorder", response_model=CustomerOrderOut)
def reorder_previous_order(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    old_order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not old_order:
        raise HTTPException(status_code=404, detail="Original order not found")
    
    old_items = db.query(OrderItem).filter(OrderItem.order_id == old_order.id).all()
    
    payload = CustomerOrderCreate(
        items=[CustomerOrderItemCreate(service_id=item.service_id, quantity=item.quantity) for item in old_items],
        pickup_address=old_order.pickup_address,
        delivery_address=old_order.delivery_address,
        pickup_date=datetime.utcnow() + timedelta(days=1),
        is_express=old_order.is_express
    )
    return place_order(payload, current_customer, db)

# ── 4. PICKUP & DELIVERY ──────────────────────────────────
@router.get("/orders/{id}/pickup")
def get_pickup_details(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    delivery = db.query(Delivery).filter(
        Delivery.order_id == id,
        Delivery.type == "PICKUP"
    ).first()
    
    if not delivery:
        return {"status": "NOT_ASSIGNED", "pickup_date": order.pickup_date}
        
    driver = db.query(User).filter(User.id == delivery.delivery_boy_id).first() if delivery.delivery_boy_id else None
    
    return {
        "status": delivery.status,
        "pickup_date": order.pickup_date,
        "driver_name": driver.name if driver else None,
        "driver_phone": driver.phone if driver else None
    }

@router.get("/orders/{id}/delivery")
def get_delivery_details(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    delivery = db.query(Delivery).filter(
        Delivery.order_id == id,
        Delivery.type == "DELIVERY"
    ).first()
    
    if not delivery:
        return {"status": "NOT_ASSIGNED", "estimated_delivery_date": order.estimated_delivery_date}
        
    driver = db.query(User).filter(User.id == delivery.delivery_boy_id).first() if delivery.delivery_boy_id else None
    
    return {
        "status": delivery.status,
        "estimated_delivery_date": order.estimated_delivery_date,
        "driver_name": driver.name if driver else None,
        "driver_phone": driver.phone if driver else None
    }

@router.get("/orders/{id}/delivery-otp")
def get_delivery_otp(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    from app.models.delivery import Delivery
    order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    delivery = db.query(Delivery).filter(
        Delivery.order_id == id,
        Delivery.type == "DELIVERY"
    ).first()
    
    if not delivery:
        raise HTTPException(status_code=404, detail="No delivery scheduled/assigned yet")
        
    if not delivery.otp:
        delivery.otp = str(random.randint(100000, 999999))
        db.commit()
        
    return {"otp": delivery.otp}

# ── 5. PAYMENTS ──────────────────────────────────────────
@router.get("/payments", response_model=List[CustomerPaymentOut])
def get_payment_history(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    payments = db.query(Payment).join(Order).filter(Order.customer_id == current_customer.id).all()
    return payments

@router.get("/payments/pending")
def get_pending_payments(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    pending = db.query(Order).filter(
        Order.customer_id == current_customer.id,
        Order.payment_status != "PAID",
        Order.status != "CANCELLED"
    ).all()
    return [{"order_id": o.id, "order_number": o.order_number, "amount_due": o.total_amount} for o in pending]

@router.post("/payments", response_model=CustomerPaymentOut)
def make_payment(
    payload: CustomerPaymentCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == payload.order_id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if payload.method == "WALLET":
        if current_customer.wallet_balance < payload.amount:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        current_customer.wallet_balance -= payload.amount
        
    payment = Payment(
        id=uuid4(),
        tenant_id=current_customer.tenant_id,
        order_id=order.id,
        amount=payload.amount,
        method=payload.method,
        status="SUCCESS"
    )
    
    order.paid_amount += payload.amount
    if order.paid_amount >= order.total_amount:
        order.payment_status = "PAID"
        
    # Earn loyalty points (1 point per 10 spent)
    points_earned = int(float(payload.amount) / 10.0)
    current_customer.loyalty_points += points_earned
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment

# ── 6. WALLET ────────────────────────────────────────────
@router.get("/wallet")
def get_wallet_details(current_customer: Customer = Depends(get_current_customer)):
    return {
        "balance": current_customer.wallet_balance,
        "currency": "USD"
    }

@router.post("/wallet/pay")
def pay_using_wallet(
    payload: WalletPayPayload,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    return make_payment(
        CustomerPaymentCreate(order_id=payload.order_id, amount=payload.amount, method="WALLET"),
        current_customer,
        db
    )

# ── 7. LOYALTY ───────────────────────────────────────────
@router.get("/loyalty")
def get_loyalty_details(current_customer: Customer = Depends(get_current_customer)):
    return {
        "points": current_customer.loyalty_points,
        "value_per_point": 0.10  # 10 points = 1 USD
    }

@router.post("/loyalty/redeem")
def redeem_loyalty_points(
    payload: LoyaltyRedeemPayload,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    if current_customer.loyalty_points < payload.points:
        raise HTTPException(status_code=400, detail="Not enough loyalty points")
        
    discount = float(payload.points) * 0.10
    current_customer.loyalty_points -= payload.points
    current_customer.wallet_balance += discount
    db.commit()
    return {
        "success": True, 
        "redeemed_points": payload.points, 
        "added_wallet_balance": discount,
        "new_loyalty_balance": current_customer.loyalty_points
    }

# ── 8. COUPONS ───────────────────────────────────────────
@router.get("/coupons")
def list_available_coupons(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    coupons = db.query(Coupon).filter(
        Coupon.tenant_id == current_customer.tenant_id,
        Coupon.expiry_date >= datetime.utcnow().date()
    ).all()
    return coupons

# ── 9. INVOICES ──────────────────────────────────────────
@router.get("/invoices")
def list_my_invoices(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    invoices = db.query(Invoice).join(Order).filter(Order.customer_id == current_customer.id).all()
    return invoices

@router.get("/invoices/{id}")
def get_invoice_details(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).join(Order).filter(
        Invoice.id == id,
        Order.customer_id == current_customer.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.get("/invoices/{id}/download")
def download_invoice_pdf(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    invoice = db.query(Invoice).join(Order).filter(
        Invoice.id == id,
        Order.customer_id == current_customer.id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    order = db.query(Order).filter(Order.id == invoice.order_id).first()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(60, 80, 120)
    pdf.set_fill_color(240, 245, 255)
    pdf.cell(0, 8, "CUSTOMER INVOICE PORTAL", ln=True, align="C", fill=True)
    pdf.ln(10)
    
    pdf.set_font("helvetica", "", 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(100, 8, text=f"Invoice Number: {invoice.invoice_number}", ln=True)
    pdf.cell(100, 8, text=f"Order Number: {order.order_number if order else 'N/A'}", ln=True)
    pdf.cell(100, 8, text=f"Amount: {invoice.amount} USD", ln=True)
    pdf.cell(100, 8, text=f"Payment Status: {invoice.status}", ln=True)
    
    pdf_bytes = bytes(pdf.output())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice.invoice_number}.pdf"}
    )

# ── 9.5 ANNOUNCEMENTS ─────────────────────────────────────
@router.get("/announcements")
def get_customer_announcements(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    from app.models.announcement import Announcement
    
    # 1. Company Admin Announcements for Customers
    company_anns = db.query(Announcement).filter(
        Announcement.tenant_id == current_customer.tenant_id,
        Announcement.status == "PUBLISHED",
        Announcement.target_audience.in_(["CUSTOMERS", "ALL"])
    ).all()
    
    # 2. Super Admin Announcements
    super_anns_query = db.query(Announcement).filter(
        Announcement.tenant_id == None,
        Announcement.status == "PUBLISHED",
        Announcement.target_audience.in_(["CUSTOMERS", "ALL"])
    ).all()
    
    customer_tenant_str = str(current_customer.tenant_id)
    valid_super_anns = []
    for ann in super_anns_query:
        if not ann.target_companies:
            valid_super_anns.append(ann)
        else:
            targets = [t.strip() for t in ann.target_companies.split(",") if t.strip()]
            if customer_tenant_str in targets:
                valid_super_anns.append(ann)
                
    return sorted(company_anns + valid_super_anns, key=lambda x: x.scheduled_at, reverse=True)

# ── 10. NOTIFICATIONS ────────────────────────────────────
@router.get("/notifications")
def get_my_notifications(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    notifs = db.query(Notification).filter(
        Notification.user_id == current_customer.id
    ).order_by(Notification.created_at.desc()).all()
    return notifs

@router.get("/notifications/unread-count")
def get_unread_notification_count(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    count = db.query(Notification).filter(
        Notification.user_id == current_customer.id,
        Notification.is_read == False
    ).count()
    return {"unread_count": count}

@router.patch("/notifications/{id}/read")
def read_notification(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    notif = db.query(Notification).filter(
        Notification.id == id,
        Notification.user_id == current_customer.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"success": True}

@router.patch("/notifications/read-all")
def read_all_notifications(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    db.query(Notification).filter(
        Notification.user_id == current_customer.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"success": True}

# ── 11. ADDRESSES ────────────────────────────────────────
@router.get("/addresses")
def get_saved_addresses(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    return db.query(CustomerAddress).filter(CustomerAddress.customer_id == current_customer.id).all()

@router.post("/addresses")
def add_new_address(
    payload: AddressCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    if payload.is_default:
        db.query(CustomerAddress).filter(
            CustomerAddress.customer_id == current_customer.id
        ).update({"is_default": False})
        
    addr = CustomerAddress(
        id=uuid4(),
        tenant_id=current_customer.tenant_id,
        customer_id=current_customer.id,
        label=payload.label,
        address_line=payload.address_line,
        is_default=payload.is_default
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr

@router.put("/addresses/{id}")
def edit_address(
    id: UUID,
    payload: AddressUpdate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    addr = db.query(CustomerAddress).filter(
        CustomerAddress.id == id,
        CustomerAddress.customer_id == current_customer.id
    ).first()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
        
    if payload.is_default:
        db.query(CustomerAddress).filter(
            CustomerAddress.customer_id == current_customer.id
        ).update({"is_default": False})
        addr.is_default = True
        
    if payload.label is not None:
        addr.label = payload.label
    if payload.address_line is not None:
        addr.address_line = payload.address_line
        
    db.commit()
    db.refresh(addr)
    return addr

@router.delete("/addresses/{id}")
def delete_address(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    addr = db.query(CustomerAddress).filter(
        CustomerAddress.id == id,
        CustomerAddress.customer_id == current_customer.id
    ).first()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
    db.delete(addr)
    db.commit()
    return {"success": True, "message": "Address deleted"}

@router.patch("/addresses/{id}/default")
def set_default_address(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    db.query(CustomerAddress).filter(
        CustomerAddress.customer_id == current_customer.id
    ).update({"is_default": False})
    
    addr = db.query(CustomerAddress).filter(
        CustomerAddress.id == id,
        CustomerAddress.customer_id == current_customer.id
    ).first()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
    addr.is_default = True
    db.commit()
    return {"success": True}

# ── 12. REVIEWS ──────────────────────────────────────────
@router.post("/orders/{id}/review")
def review_order(
    id: UUID,
    payload: CustomerReviewCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == id, Order.customer_id == current_customer.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.rating = payload.rating
    order.review = payload.comment
    
    # Also add into Review model
    rev = Review(
        id=uuid4(),
        tenant_id=current_customer.tenant_id,
        customer_id=current_customer.id,
        order_id=order.id,
        rating=payload.rating,
        comment=payload.comment
    )
    db.add(rev)
    db.commit()
    return {"success": True, "message": "Review submitted"}

@router.get("/reviews", response_model=List[CustomerReviewOut])
def get_my_reviews(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    orders = db.query(Order).filter(
        Order.customer_id == current_customer.id,
        Order.rating.isnot(None)
    ).all()
    return orders

@router.put("/reviews/{id}")
def edit_my_review(
    id: UUID,
    payload: CustomerReviewCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    rev = db.query(Review).filter(
        Review.id == id,
        Review.customer_id == current_customer.id
    ).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found")
    rev.rating = payload.rating
    rev.comment = payload.comment
    db.commit()
    return {"success": True, "message": "Review updated"}

# ── 13. SUPPORT ──────────────────────────────────────────
@router.post("/support/tickets")
def create_support_ticket(
    payload: CustomerTicketCreate,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    ticket = SupportTicket(
        id=uuid4(),
        tenant_id=current_customer.tenant_id,
        user_id=current_customer.id,
        subject=payload.subject,
        description=payload.description,
        status="OPEN",
        priority=payload.priority.upper()
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.get("/support/tickets")
def list_my_tickets(
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    tickets = db.query(SupportTicket).filter(SupportTicket.user_id == current_customer.id).all()
    return tickets

@router.get("/support/tickets/{id}")
def get_ticket_details(
    id: UUID,
    current_customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == id,
        SupportTicket.user_id == current_customer.id
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

# ── 14. QR CODE ACCESS ────────────────────────────────────
@router.get("/my-qr")
def get_my_qr_code(current_customer: Customer = Depends(get_current_customer)):
    from app.core.security import create_access_token
    token = create_access_token(
        subject=f"{current_customer.id}:{current_customer.qr_secret}", 
        role="CUSTOMER", 
        tenant_id=str(current_customer.tenant_id)
    )
    portal_url = f"https://portal.laundry.com/login?token={token}"
    return {
        "customer_id": current_customer.id,
        "portal_url": portal_url
    }
