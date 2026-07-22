from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from typing import List
import uuid
import datetime

from app.core.database import get_db
from app.models.user import User
from app.models.prepaid_package import PrepaidPackage
from app.models.customer_package import CustomerPackage
from app.models.package_usage_history import PackageUsageHistory
from app.schemas.prepaid_package import (
    PrepaidPackageCreate, PrepaidPackageResponse,
    CustomerPackageCreate, CustomerPackageResponse,
    PackageRedeemRequest
)
from app.dependencies import get_current_user, get_current_admin
from app.models.coupon import Coupon
from app.models.wallet_pass import WalletPass
from app.models.payment import Payment
from app.services.wallet_service import WalletService
from app.services.whatsapp_service import WhatsAppService
from app.wallet.object_manager import build_wallet_object_payload, generate_google_wallet_save_url

router = APIRouter()

@router.post("/", response_model=PrepaidPackageResponse, status_code=201)
def create_prepaid_package(
    payload: PrepaidPackageCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Admin creates a new prepaid package definition"""
    new_pkg = PrepaidPackage(
        tenant_id=current_admin.tenant_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        original_price=payload.original_price,
        offer_price=payload.offer_price,
        total_quantity=payload.total_quantity,
        eligible_services=payload.eligible_services,
        validity_days=payload.validity_days,
        start_date=payload.start_date,
        expiry_date=payload.expiry_date,
        is_active=payload.is_active
    )
    db.add(new_pkg)
    db.commit()
    db.refresh(new_pkg)
    return new_pkg

@router.get("/", response_model=List[PrepaidPackageResponse])
def list_prepaid_packages(
    db: Session = Depends(get_db),
    # Note: Using get_current_user so both admin and customer can view available packages
    current_user: User = Depends(get_current_user)
):
    """List all available prepaid packages for a tenant"""
    pkgs = db.query(PrepaidPackage).filter(
        PrepaidPackage.tenant_id == current_user.tenant_id,
        PrepaidPackage.is_active == True
    ).all()
    return pkgs

@router.put("/{package_id}", response_model=PrepaidPackageResponse)
def update_prepaid_package(
    package_id: uuid.UUID,
    payload: PrepaidPackageCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Admin updates an existing prepaid package"""
    pkg = db.query(PrepaidPackage).filter(
        PrepaidPackage.id == package_id,
        PrepaidPackage.tenant_id == current_admin.tenant_id
    ).first()
    
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
        
    pkg.name = payload.name
    pkg.code = payload.code
    pkg.description = payload.description
    pkg.original_price = payload.original_price
    pkg.offer_price = payload.offer_price
    pkg.total_quantity = payload.total_quantity
    pkg.eligible_services = payload.eligible_services
    pkg.validity_days = payload.validity_days
    pkg.start_date = payload.start_date
    pkg.expiry_date = payload.expiry_date
    pkg.is_active = payload.is_active
    
    db.commit()
    db.refresh(pkg)
    return pkg

@router.delete("/{package_id}")
def delete_prepaid_package(
    package_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Admin deletes (or deactivates) a prepaid package"""
    pkg = db.query(PrepaidPackage).filter(
        PrepaidPackage.id == package_id,
        PrepaidPackage.tenant_id == current_admin.tenant_id
    ).first()
    
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
        
    pkg.is_active = False # soft delete
    db.commit()
    return {"message": "Package deleted successfully"}

from app.schemas.prepaid_package import CustomerPackageResponse, WalletGenerationStatus

@router.post("/purchase", response_model=CustomerPackageResponse, status_code=201)
def purchase_package(
    payload: CustomerPackageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # Can be purchased by Customer or assigned by Admin
):
    """Customer purchases a prepaid package"""
    pkg = db.query(PrepaidPackage).filter(
        PrepaidPackage.id == payload.package_id,
        PrepaidPackage.tenant_id == current_user.tenant_id
    ).first()
    
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
        
    activation_date = datetime.datetime.utcnow()
    expiry_date = None
    if pkg.validity_days:
        expiry_date = activation_date + datetime.timedelta(days=pkg.validity_days)
    elif pkg.expiry_date:
        expiry_date = datetime.datetime.combine(pkg.expiry_date, datetime.time.max)
        
    final_price = float(pkg.offer_price)
    if payload.coupon_code:
        import datetime as dt
        today = dt.date.today()
        coupon = db.query(Coupon).filter(
            Coupon.code == payload.coupon_code,
            Coupon.tenant_id == current_user.tenant_id
        ).first()
        if coupon:
            if coupon.expiry_date and coupon.expiry_date < today:
                raise HTTPException(status_code=400, detail="Coupon has expired")
            if coupon.start_date and coupon.start_date > today:
                raise HTTPException(status_code=400, detail="Coupon is not active yet")
            
            val = float(coupon.value)
            if coupon.discount_type == "PERCENTAGE":
                discount = final_price * (val / 100.0)
            elif coupon.discount_type == "FLAT":
                discount = val
            else:
                discount = 0.0
            final_price = max(0.0, final_price - discount)
    
    # 1. Save CustomerPackage Purchase (Wallet balance is the full original package value)
    full_pkg_value = float(pkg.original_price) if pkg.original_price and float(pkg.original_price) > 0 else float(pkg.offer_price)
    customer_pkg = CustomerPackage(
        id=uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        customer_id=payload.customer_id,
        package_id=pkg.id,
        purchase_date=activation_date,
        activation_date=activation_date,
        expiry_date=expiry_date,
        total_quantity=pkg.total_quantity,
        used_quantity=0,
        package_value=full_pkg_value,
        current_balance=full_pkg_value,
        used_amount=0.0,
        pass_color="GOLD",
        status="ACTIVE"
    )
    db.add(customer_pkg)
    db.commit()
    db.refresh(customer_pkg)
    
    customer_pkg = db.query(CustomerPackage).options(joinedload(CustomerPackage.package)).filter(CustomerPackage.id == customer_pkg.id).first()
    customer = db.query(User).filter(User.id == payload.customer_id).first()
    company_name = getattr(current_user, 'company', None).name if getattr(current_user, 'company', None) else "Laundra Laundry"

    # 2. Orchestrate Google Wallet, Apple Wallet, QR Code Creation & DB Persistence
    wallet_status = {"google_wallet": False, "apple_wallet": False, "qr_code": False}
    try:
        wallet_status = WalletService.create_and_save_wallet_pass(
            db=db,
            package=customer_pkg,
            customer=customer,
            company_name=company_name
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Unexpected error in wallet orchestration for package {customer_pkg.id}: {e}")

    # 3. Trigger WhatsApp Notification
    if customer:
        try:
            WhatsAppService.send_package_activated_message(customer, customer_pkg)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send WhatsApp notification for package {customer_pkg.id}: {e}")
        
    setattr(customer_pkg, "wallet_generation", wallet_status)
    return customer_pkg

@router.get("/customer/{customer_id}", response_model=List[CustomerPackageResponse])
def get_customer_packages(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all purchased packages for a specific customer"""
    pkgs = db.query(CustomerPackage).options(joinedload(CustomerPackage.package)).filter(
        CustomerPackage.customer_id == customer_id,
        CustomerPackage.tenant_id == current_user.tenant_id
    ).order_by(CustomerPackage.purchase_date.desc()).all()
    
    # Auto-update status for expired ones & generate missing wallet URLs before returning
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    customer = db.query(User).filter(User.id == customer_id).first()
    company_name = getattr(current_user, 'company', None).name if getattr(current_user, 'company', None) else "Laundra Laundry"

    for p in pkgs:
        if p.status == "ACTIVE":
            if p.expiry_date:
                exp_date_aware = p.expiry_date
                if exp_date_aware.tzinfo is None:
                    exp_date_aware = exp_date_aware.replace(tzinfo=datetime.timezone.utc)
                if now > exp_date_aware:
                    p.status = "EXPIRED"
                    db.commit()
                    continue

            if (not p.google_wallet_url or not p.apple_wallet_url) and customer:
                try:
                    WalletService.create_and_save_wallet_pass(
                        db=db,
                        package=p,
                        customer=customer,
                        company_name=company_name
                    )
                    db.refresh(p)
                except Exception as e:
                    print(f"Could not generate wallet pass on the fly: {e}")

    return pkgs

@router.get("/qr/{secure_token}")
def get_package_by_qr_token(
    secure_token: str,
    db: Session = Depends(get_db)
    # Public endpoint for scanning QR codes
):
    """Public endpoint to view package details via QR Scan"""
    pkg = db.query(CustomerPackage).options(joinedload(CustomerPackage.package), joinedload(CustomerPackage.customer)).filter(
        CustomerPackage.secure_token == secure_token
    ).first()
    
    if not pkg:
        raise HTTPException(status_code=404, detail="Invalid QR Code")
        
    usage_history = db.query(PackageUsageHistory).filter(
        PackageUsageHistory.customer_package_id == pkg.id
    ).order_by(PackageUsageHistory.transaction_date.desc()).all()
    
    return {
        "customer": {
            "id": pkg.customer.id,
            "name": pkg.customer.name,
            "phone": pkg.customer.phone,
            "email": pkg.customer.email
        },
        "package": {
            "id": pkg.id,
            "name": pkg.package.name,
            "type": pkg.package.code,
            "purchase_date": pkg.purchase_date,
            "activation_date": pkg.activation_date,
            "expiry_date": pkg.expiry_date,
            "status": pkg.status,
            "total_quantity": pkg.total_quantity,
            "used_quantity": pkg.used_quantity,
            "remaining_quantity": pkg.total_quantity - pkg.used_quantity,
            "original_price": pkg.package.original_price,
            "offer_price": pkg.package.offer_price,
            "eligible_services": pkg.package.eligible_services,
            "secure_token": pkg.secure_token
        },
        "history": [
            {
                "id": h.id,
                "order_id": h.order_id,
                "quantity_used": h.quantity_used,
                "transaction_date": h.transaction_date
            } for h in usage_history
        ]
    }

@router.post("/redeem", status_code=200)
def redeem_package_quantity(
    payload: PackageRedeemRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Cashier redeems package quantity during POS checkout"""
    pkg = db.query(CustomerPackage).filter(
        CustomerPackage.secure_token == payload.secure_token,
        CustomerPackage.tenant_id == current_admin.tenant_id
    ).first()
    
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
        
    if pkg.status != "ACTIVE":
        raise HTTPException(status_code=400, detail=f"Package cannot be redeemed. Status is {pkg.status}")
        
    if pkg.expiry_date:
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        exp_date_aware = pkg.expiry_date
        if exp_date_aware.tzinfo is None:
            exp_date_aware = exp_date_aware.replace(tzinfo=datetime.timezone.utc)
        if now > exp_date_aware:
            pkg.status = "EXPIRED"
            db.commit()
            raise HTTPException(status_code=400, detail="Package is expired")
            
    remaining = pkg.total_quantity - pkg.used_quantity
    if payload.quantity_used > remaining:
        raise HTTPException(status_code=400, detail=f"Insufficient package balance. Only {remaining} items remaining.")
        
    # Deduct
    pkg.used_quantity += payload.quantity_used
    if pkg.used_quantity >= pkg.total_quantity:
        pkg.status = "FULLY_UTILIZED"
        
    # Record history
    history = PackageUsageHistory(
        tenant_id=current_admin.tenant_id,
        customer_package_id=pkg.id,
        order_id=payload.order_id,
        quantity_used=payload.quantity_used
    )
    db.add(history)
    db.commit()

    # Step 8: Update Google Wallet Object pass balance & status
    customer = db.query(User).filter(User.id == pkg.customer_id).first()
    WalletService.update_wallet_pass_on_usage(db, pkg, customer)
    
    return {"success": True, "message": f"Successfully redeemed {payload.quantity_used} items.", "remaining": pkg.total_quantity - pkg.used_quantity}
