from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import uuid4, UUID
from decimal import Decimal
from pydantic import BaseModel

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_admin_or_cashier, check_subscription_active, get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.models.order import Order
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerPublicOut
from app.schemas.order import OrderOut
from app.repositories.customer_repository import CustomerRepository

router = APIRouter()
customer_repo = CustomerRepository()

class WalletUpdate(BaseModel):
    amount: Decimal

class LoyaltyUpdate(BaseModel):
    points: int

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

class EmailOTPRequest(BaseModel):
    email: str
    phone: Optional[str] = None

@router.post("/send-otp")
def send_otp_for_creation(
    payload: EmailOTPRequest,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    """
    Admin sends OTP to customer/user email before manual creation.
    The email is sent using Super Admin's platform SMTP settings.
    """
    import random
    from app.api.v1.auth import MOCK_OTP_STORE
    from app.core.email_service import send_otp_email
    
    # Pre-validate duplicates before sending OTP
    if payload.phone:
        existing = db.query(Customer).filter(
            Customer.phone == payload.phone,
            Customer.tenant_id == current_admin.tenant_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer with this phone number already exists under this tenant"
            )
            
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    
    otp = str(random.randint(100000, 999999))
    MOCK_OTP_STORE[payload.email] = otp
    
    # Send real email using Super Admin's platform SMTP
    email_sent = send_otp_email(db, payload.email, otp)
    
    response = {"message": f"OTP sent successfully to {payload.email}"}
    if not email_sent:
        response["warning"] = "Platform SMTP not configured. Contact Super Admin."
        response["otp_debug"] = otp
    
    return response

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

@router.post("/verify-otp")
def verify_otp_only(payload: VerifyOTPRequest):
    from app.api.v1.auth import MOCK_OTP_STORE
    stored_otp = MOCK_OTP_STORE.get(payload.email)
    if not stored_otp or stored_otp != payload.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code"
        )
    return {"message": "OTP verified successfully"}

@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_in: CustomerCreate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db),
    _sub: bool = Depends(check_subscription_active)
):
    from app.api.v1.auth import MOCK_OTP_STORE
    
    existing = db.query(Customer).filter(
        Customer.phone == customer_in.phone,
        Customer.tenant_id == current_admin.tenant_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer with this phone number already exists under this tenant"
        )
        
    # Enforce subscription customer limit
    from app.core.subscription_limits import check_customer_limit
    check_customer_limit(db, current_admin.tenant_id)

    if customer_in.email:
        # Check duplicate User email
        existing_user = db.query(User).filter(User.email == customer_in.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered"
            )
        
    user_id = uuid4()
    from app.core.security import get_password_hash
    
    # Create the User record (only if email is provided, since email is used for login)
    if customer_in.email:
        new_user = User(
            id=user_id,
            tenant_id=current_admin.tenant_id,
            name=customer_in.name,
            phone=customer_in.phone,
            email=customer_in.email,
            password=get_password_hash(customer_in.password or "customer123"),
            role="CUSTOMER",
            status="ACTIVE"
        )
        db.add(new_user)
    
    import uuid
    # Create the Customer record
    new_customer = Customer(
        id=user_id,
        tenant_id=current_admin.tenant_id,
        name=customer_in.name,
        phone=customer_in.phone,
        email=customer_in.email,
        address=customer_in.address or "",
        wallet_balance=Decimal("0.0"),
        loyalty_points=0,
        qr_secret=uuid.uuid4().hex,
        referral_code=customer_in.referral_code,
        gender=customer_in.gender,
        dob=customer_in.dob,
        gst_number=customer_in.gst_number,
        notes=customer_in.notes
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    
    if customer_in.email:
        MOCK_OTP_STORE.pop(customer_in.email, None)
    return new_customer

@router.get("", response_model=List[CustomerOut])
def list_customers(
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    return customer_repo.get_multi(db, tenant_id=current_admin.tenant_id)

@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    return customer

@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Exclude unset fields
    update_data = payload.model_dump(exclude_unset=True)
    return customer_repo.update(db, db_obj=customer, obj_in=update_data)

@router.delete("/{customer_id}", status_code=status.HTTP_200_OK)
def delete_customer(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    # Delete all dependent records to avoid FK violations
    try:
        from app.models.review import Review
        db.query(Review).filter(Review.customer_id == customer_id).delete(synchronize_session=False)
    except Exception:
        pass

    try:
        from app.models.customer_support_ticket import CustomerSupportTicket
        db.query(CustomerSupportTicket).filter(CustomerSupportTicket.customer_id == customer_id).delete(synchronize_session=False)
    except Exception:
        pass

    try:
        from app.models.customer_address import CustomerAddress
        db.query(CustomerAddress).filter(CustomerAddress.customer_id == customer_id).delete(synchronize_session=False)
    except Exception:
        pass

    try:
        db.query(Order).filter(Order.customer_id == customer_id).delete(synchronize_session=False)
    except Exception:
        pass

    # Delete associated user login record
    associated_user = db.query(User).filter(User.email == customer.email, User.role == "CUSTOMER").first()
    if associated_user:
        db.delete(associated_user)

    # Delete customer record
    db.query(Customer).filter(Customer.id == customer_id).delete(synchronize_session=False)
    db.commit()
    return {"success": True, "message": "Customer and all associated data deleted successfully"}

@router.delete("/by-email/{email}", status_code=status.HTTP_200_OK)
def delete_customer_by_email(
    email: str,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    customer = db.query(Customer).filter(Customer.email == email, Customer.tenant_id == current_admin.tenant_id).first()
    if customer:
        customer_repo.remove(db, id=customer.id)
        
    associated_user = db.query(User).filter(User.email == email, User.role == "CUSTOMER", User.tenant_id == current_admin.tenant_id).first()
    if associated_user:
        db.delete(associated_user)
        
    db.commit()
    return {"success": True, "message": "Customer deleted successfully"}

@router.get("/{customer_id}/orders", response_model=List[OrderOut])
def get_customer_order_history(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    orders = db.query(Order).filter(
        Order.customer_id == customer_id,
        Order.tenant_id == current_admin.tenant_id
    ).all()
    
    # Populate items for order schemas
    from app.models.order_item import OrderItem
    for o in orders:
        o.items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        
    return orders

@router.get("/{customer_id}/wallet")
def get_customer_wallet(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    return {
        "customer_id": customer.id,
        "wallet_balance": customer.wallet_balance,
        "loyalty_points": customer.loyalty_points
    }

@router.get("/{customer_id}/wallet-public")
def get_customer_wallet_public(
    customer_id: UUID,
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    return {
        "customer_id": customer.id,
        "wallet_balance": customer.wallet_balance,
        "loyalty_points": customer.loyalty_points
    }

@router.post("/{customer_id}/wallet", response_model=CustomerOut)
def update_wallet_balance(
    customer_id: UUID,
    payload: WalletUpdate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    customer.wallet_balance += payload.amount
    db.commit()
    db.refresh(customer)
    return customer

@router.post("/{customer_id}/add-funds", response_model=CustomerOut)
def customer_add_funds(
    customer_id: UUID,
    payload: WalletUpdate,
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    customer.wallet_balance += payload.amount
    db.commit()
    db.refresh(customer)
    return customer

@router.post("/{customer_id}/loyalty", response_model=CustomerOut)
def update_loyalty_points(
    customer_id: UUID,
    payload: LoyaltyUpdate,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    customer.loyalty_points = max(0, customer.loyalty_points + payload.points)
    db.commit()
    db.refresh(customer)
    return customer

class AddressCreatePayload(BaseModel):
    label: str
    address_line: str
    is_default: bool = False

@router.get("/me/addresses")
def get_my_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customer accounts can manage saved addresses"
        )
        
    from app.models.customer_address import CustomerAddress
    return db.query(CustomerAddress).filter(
        CustomerAddress.customer_id == current_user.id
    ).all()

@router.post("/me/addresses")
def add_my_address(
    payload: AddressCreatePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customer accounts can manage saved addresses"
        )
        
    from app.models.customer_address import CustomerAddress
    from uuid import uuid4
    
    if payload.is_default:
        db.query(CustomerAddress).filter(
            CustomerAddress.customer_id == current_user.id
        ).update({"is_default": False})
        
    addr = CustomerAddress(
        id=uuid4(),
        tenant_id=current_user.tenant_id,
        customer_id=current_user.id,
        label=payload.label,
        address_line=payload.address_line,
        is_default=payload.is_default
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr

@router.delete("/me/addresses/{address_id}")
def delete_my_address(
    address_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customer accounts can manage saved addresses"
        )
        
    from app.models.customer_address import CustomerAddress
    addr = db.query(CustomerAddress).filter(
        CustomerAddress.id == address_id,
        CustomerAddress.customer_id == current_user.id
    ).first()
    if not addr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
        
    db.delete(addr)
    db.commit()
    return {"success": True, "message": "Address deleted successfully"}

@router.get("/me/referrals")
def get_my_referral_details(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "CUSTOMER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customer accounts have referral parameters"
        )
        
    customer = db.query(Customer).filter(Customer.id == current_user.id).first()
    if not customer.referral_code:
        import random
        import string
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        customer.referral_code = f"REF-{code}"
        db.commit()
        db.refresh(customer)
        
    referred_count = db.query(Customer).filter(Customer.referred_by_id == customer.id).count()
    
    return {
        "referral_code": customer.referral_code,
        "referred_count": referred_count,
        "reward_points_per_referral": 50
    }

import qrcode
import base64
from io import BytesIO
from urllib.parse import quote

@router.get("/{customer_id}/qr")
def generate_customer_qr(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    from app.core.security import create_access_token
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    if not customer.qr_secret:
        import uuid
        customer.qr_secret = uuid.uuid4().hex
        db.commit()
        
    # Generate a secure JWT token for auto-login
    token = create_access_token(
        subject=f"{customer.id}:{customer.qr_secret}", 
        role="CUSTOMER", 
        tenant_id=str(customer.tenant_id)
    )
    portal_url = f"https://portal.laundry.com/login?token={token}"
    
    # Generate physical QR code image (Base64 PNG)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(portal_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return {
        "customer_id": customer.id,
        "portal_url": portal_url,
        "qr_image_base64": f"data:image/png;base64,{img_str}"
    }

@router.get("/{customer_id}/qr/image")
def get_customer_qr_image(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    """Returns the QR code directly as a PNG image. 
    Open this URL in a browser to view/download the QR code."""
    from app.core.security import create_access_token
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    if not customer.qr_secret:
        import uuid
        customer.qr_secret = uuid.uuid4().hex
        db.commit()
        
    token = create_access_token(
        subject=f"{customer.id}:{customer.qr_secret}", 
        role="CUSTOMER", 
        tenant_id=str(customer.tenant_id)
    )
    portal_url = f"https://portal.laundry.com/login?token={token}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(portal_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    
    return Response(
        content=buffered.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=qr_{customer_id}.png"}
    )

@router.get("/{customer_id}/share-wa")
def share_qr_whatsapp(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    from app.core.security import create_access_token
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    if not customer.qr_secret:
        import uuid
        customer.qr_secret = uuid.uuid4().hex
        db.commit()
        
    token = create_access_token(
        subject=f"{customer.id}:{customer.qr_secret}", 
        role="CUSTOMER", 
        tenant_id=str(customer.tenant_id)
    )
    portal_url = f"https://portal.laundry.com/login?token={token}"
    
    message = f"Hello {customer.name}!\n\nAccess your Laundry Portal securely using this link:\n{portal_url}\n\nThank you for choosing us!"
    encoded_message = quote(message)
    
    wa_link = f"https://wa.me/{customer.phone}?text={encoded_message}"
    
    customer.qr_status = "SHARED_VIA_WHATSAPP"
    db.commit()
    
    return {
        "customer_id": customer.id,
        "whatsapp_url": wa_link
    }

@router.post("/{customer_id}/qr/regenerate")
def regenerate_qr(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    import uuid
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    customer.qr_secret = uuid.uuid4().hex
    customer.qr_status = "REGENERATED"
    db.commit()
    return {"success": True, "message": "Customer QR regenerated successfully. Old QR codes are now disabled."}

@router.post("/{customer_id}/qr/disable")
def disable_qr(
    customer_id: UUID,
    current_admin: User = Depends(get_current_admin_or_cashier),
    db: Session = Depends(get_db)
):
    customer = customer_repo.get(db, customer_id, tenant_id=current_admin.tenant_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    customer.qr_secret = None
    customer.qr_status = "DISABLED"
    db.commit()
    return {"success": True, "message": "Customer QR disabled successfully. The customer cannot log in via QR until a new one is generated."}

@router.get("/public/{customer_id}", response_model=CustomerPublicOut)
def get_public_customer(
    customer_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Public endpoint used by the Customer Portal magic link to load customer data 
    without requiring an admin token or password login.
    """
    customer = customer_repo.get(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    from app.core.security import create_access_token
    token = create_access_token(
        subject=customer.id,
        role="CUSTOMER",
        tenant_id=customer.tenant_id
    )
    customer.access_token = token
    customer.token_type = "Bearer"
    return customer
