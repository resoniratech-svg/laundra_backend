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
        order_id: UUID,
        delivery_boy_id: UUID = None,
        delivery_type: str,  # PICKUP / DELIVERY
        tenant_id: UUID = None
    ) -> Delivery:
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        if not tenant_id:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant context not found"
            )

        # 1. Verify Order
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.tenant_id == tenant_id
        ).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        # 2. Verify Delivery Boy if provided
        if delivery_boy_id:
            boy = db.query(User).filter(
                User.id == delivery_boy_id,
                User.tenant_id == tenant_id,
                User.role == "DELIVERY_BOY"
            ).first()
            if not boy:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Delivery boy not found or invalid role"
                )

        # 3. Create Delivery
        delivery = Delivery(
            id=uuid4(),
            tenant_id=tenant_id,
            order_id=order_id,
            delivery_boy_id=delivery_boy_id,
            type=delivery_type,
            status="ASSIGNED",
            otp=DeliveryService.generate_otp()
        )
        
        # 4. Update Order Status
        if delivery_type == "PICKUP":
            order.status = "ASSIGNED"  # or OUT_FOR_PICKUP
        else:
            order.status = "OUT_FOR_DELIVERY"

        db.add(delivery)
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
