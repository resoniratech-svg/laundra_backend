from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from datetime import datetime
import random
from fastapi import HTTPException, status

from app.models.delivery import Delivery
from app.models.order import Order
from app.models.user import User
from app.core.tenant import get_current_tenant_id

class DeliveryService:
    @staticmethod
    def generate_otp() -> str:
        return "".join(random.choices("0123456789", k=4))

    @staticmethod
    def assign_delivery(
        db: Session,
        *,
        order_id: str,
        delivery_boy_id: str = None,
        courier_name: str = None,
        delivery_type: str,  # PICKUP / DELIVERY
        tenant_id: UUID = None,
        pickup_commission = None,
        delivery_commission = None
    ) -> Delivery:
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        if not tenant_id:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant context not found"
            )

        # 1. Verify Order (by UUID or string order_number)
        from sqlalchemy import or_
        clean_id = str(order_id).replace('#', '').strip()
        order = None
        try:
            from uuid import UUID as PyUUID
            val_uuid = PyUUID(clean_id)
            order = db.query(Order).filter(
                or_(Order.id == val_uuid, Order.order_number == clean_id),
                Order.tenant_id == tenant_id
            ).first()
        except (ValueError, TypeError):
            pass

        if not order:
            order = db.query(Order).filter(
                Order.order_number == clean_id,
                Order.tenant_id == tenant_id
            ).first()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        target_order_id = order.id

        # 2. Verify Delivery Boy if provided (by UUID or Name)
        boy = None
        driver_uuid = None
        resolved_name = courier_name or (str(delivery_boy_id) if delivery_boy_id else None)

        if delivery_boy_id:
            try:
                from uuid import UUID as PyUUID
                driver_uuid = PyUUID(str(delivery_boy_id))
                boy = db.query(User).filter(User.id == driver_uuid, User.tenant_id == tenant_id).first()
            except (ValueError, TypeError):
                pass

        if not boy and resolved_name:
            boy = db.query(User).filter(
                User.name.ilike(resolved_name),
                User.tenant_id == tenant_id
            ).first()
            if boy:
                driver_uuid = boy.id

        final_courier_name = (boy.name if boy else resolved_name) if resolved_name and resolved_name not in ['-- Unassigned --', 'Unassigned'] else None

        # Update courier and commission on order
        if delivery_type == "PICKUP":
            if pickup_commission is not None:
                order.pickup_commission = pickup_commission
            if final_courier_name:
                order.pickup_courier = final_courier_name
                order.pickup_staff_id = driver_uuid
        elif delivery_type == "DELIVERY":
            if delivery_commission is not None:
                order.delivery_commission = delivery_commission
            if final_courier_name:
                order.delivery_courier = final_courier_name
                order.delivery_staff_id = driver_uuid

        # 3. Check for existing active (uncompleted) Delivery record for this order and type
        existing_delivery = db.query(Delivery).filter(
            Delivery.order_id == target_order_id,
            Delivery.type == delivery_type,
            Delivery.tenant_id == tenant_id,
            ~Delivery.status.in_(["DELIVERED", "PICKED", "COMPLETED", "PARTIALLY_PICKED_UP", "PARTIALLY_DELIVERED"])
        ).first()

        if existing_delivery:
            existing_delivery.delivery_boy_id = delivery_boy_id
            existing_delivery.status = "ASSIGNED"
            if pickup_commission is not None:
                existing_delivery.pickup_commission = pickup_commission
            if delivery_commission is not None:
                existing_delivery.delivery_commission = delivery_commission
            delivery = existing_delivery
        else:
            # Create a new delivery record (first time or previous batch was completed)
            delivery = Delivery(
                id=uuid4(),
                tenant_id=tenant_id,
                order_id=target_order_id,
                delivery_boy_id=delivery_boy_id,
                type=delivery_type,
                status="ASSIGNED",
                otp=DeliveryService.generate_otp(),
                pickup_commission=pickup_commission if pickup_commission is not None else getattr(order, 'pickup_commission', None),
                delivery_commission=delivery_commission if delivery_commission is not None else getattr(order, 'delivery_commission', None)
            )
            db.add(delivery)
        
        # 4. Update Order Status
        if delivery_type == "PICKUP":
            order.status = "ASSIGNED"
        else:
            order.status = "OUT_FOR_DELIVERY"
        db.commit()
        db.refresh(delivery)
        return delivery

    @staticmethod
    def complete_delivery(
        db: Session,
        *,
        delivery_id: UUID,
        otp: str,
        photos: str = None,
        notes: str = None,
        tenant_id: UUID = None
    ) -> Delivery:
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        if not tenant_id:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant context not found"
            )

        # 1. Fetch delivery record
        delivery = db.query(Delivery).filter(
            Delivery.id == delivery_id,
            Delivery.tenant_id == tenant_id
        ).first()
        if not delivery:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery task not found"
            )

        if delivery.status == "DELIVERED":
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivery already completed"
            )

        # 2. Verify OTP
        if delivery.otp != otp:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code"
            )

        # 3. Mark Delivery completed
        delivery.status = "DELIVERED"
        delivery.delivered_at = datetime.now()
        delivery.photos = photos
        delivery.notes = notes

        # 4. Update associated Order status
        order = db.query(Order).filter(
            Order.id == delivery.order_id,
            Order.tenant_id == tenant_id
        ).first()
        if order:
            if delivery.type == "PICKUP":
                order.status = "RECEIVED"
            else:
                order.status = "DELIVERED"
                
            # Record history log
            import json
            from app.models.order_item import OrderItem
            from app.models.service import Service
            from app.models.user import User

            staff_name = "Delivery Staff"
            if delivery.delivery_boy_id:
                driver_user = db.query(User).filter(User.id == delivery.delivery_boy_id).first()
                if driver_user and driver_user.name:
                    staff_name = driver_user.name

            order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
            item_logs = []
            for oi in order_items:
                srv = db.query(Service).filter(Service.id == oi.service_id).first()
                s_name = srv.name if srv else "Laundry Item"
                qty = oi.delivered_quantity if (delivery.type == "DELIVERY" and oi.delivered_quantity and oi.delivered_quantity > 0) else (oi.picked_up_quantity if (oi.picked_up_quantity and oi.picked_up_quantity > 0) else (oi.quantity or 1))
                item_logs.append({
                    "service_name": s_name,
                    "quantity": qty
                })

            new_log_entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                "staff_name": staff_name,
                "items": item_logs
            }

            if delivery.type == "DELIVERY":
                existing_history = []
                if order.delivery_history:
                    try:
                        existing_history = json.loads(order.delivery_history) if isinstance(order.delivery_history, str) else order.delivery_history
                    except Exception:
                        existing_history = []
                existing_history.append(new_log_entry)
                order.delivery_history = json.dumps(existing_history)
            else:
                existing_history = []
                if order.pickup_history:
                    try:
                        existing_history = json.loads(order.pickup_history) if isinstance(order.pickup_history, str) else order.pickup_history
                    except Exception:
                        existing_history = []
                existing_history.append(new_log_entry)
                order.pickup_history = json.dumps(existing_history)

            # Customer Notification
            from app.models.notification import Notification
            title_text = "laundry Picked Up" if delivery.type == "PICKUP" else "laundry Delivered"
            msg_text = f"Your laundry order {order.order_number} has been successfully " + ("picked up!" if delivery.type == "PICKUP" else "delivered!")
            notif = Notification(
                id=uuid4(),
                tenant_id=tenant_id,
                user_id=order.customer_id,
                title=title_text,
                message=msg_text,
                is_read=False
            )
            db.add(notif)
            
        # Audit Log
        from app.models.audit_log import AuditLog
        action_text = f"Delivery task completed ({delivery.type}) for order {order.order_number if order else 'N/A'}"
        audit_log = AuditLog(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=delivery.delivery_boy_id or tenant_id,
            action=action_text,
            module="DELIVERIES"
        )
        db.add(audit_log)

        db.commit()
        db.refresh(delivery)
        return delivery
