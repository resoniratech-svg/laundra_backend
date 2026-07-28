from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from typing import List
from decimal import Decimal
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
from app.models.service import Service

def resolve_service_items_from_package(db: Session, pkg: PrepaidPackage) -> list:
    """
    Resolves eligible_services (which contain Service UUIDs or category dicts)
    into a grouped list of dynamic service items with exact names/categories.
    """
    if not pkg or not pkg.eligible_services or not isinstance(pkg.eligible_services, list):
        return []

    cat_totals = {}  # category_name -> quantity

    for item in pkg.eligible_services:
        svc_id = None
        qty = 1
        explicit_cat = None

        if isinstance(item, dict):
            svc_id = item.get("id") or item.get("service_id") or item.get("serviceId")
            qty = int(item.get("qty") or item.get("quantity") or 1)
            explicit_cat = item.get("category") or item.get("service") or item.get("name")
        elif isinstance(item, str):
            svc_id = item
            qty = 1

        resolved_cat = None
        # If explicit category string is provided and is not a UUID
        if explicit_cat and isinstance(explicit_cat, str) and not explicit_cat.startswith("0") and len(explicit_cat) < 40 and "-" not in explicit_cat:
            resolved_cat = explicit_cat.strip()
        elif svc_id:
            try:
                val_uuid = uuid.UUID(str(svc_id))
                svc = db.query(Service).filter(Service.id == val_uuid).first()
                if svc:
                    resolved_cat = (svc.category or svc.name or "Service").strip()
            except Exception:
                pass

        if not resolved_cat:
            resolved_cat = "General Laundry"

        cat_totals[resolved_cat] = cat_totals.get(resolved_cat, 0) + qty

    result = []
    for cat_name, total_qty in cat_totals.items():
        if total_qty > 0:
            result.append({
                "service": cat_name,
                "total": total_qty,
                "left": total_qty
            })

    return result

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
        
    discount = 0.0
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

    # Build dynamic service_items from the package's eligible_services
    dynamic_service_items = resolve_service_items_from_package(db, pkg)

    # Also populate legacy fixed columns for backward compat
    w_tot, i_tot, d_tot, s_tot = 0, 0, 0, 0
    for si in dynamic_service_items:
        cat = si["service"].lower()
        if "steam" in cat:
            s_tot += si["total"]
        elif "wash" in cat or "fold" in cat:
            w_tot += si["total"]
        elif "press" in cat or "iron" in cat:
            i_tot += si["total"]
        elif "dry" in cat or "premium" in cat:
            d_tot += si["total"]
        else:
            w_tot += si["total"]

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
        status="ACTIVE",
        wash_total=w_tot,
        wash_left=w_tot,
        iron_total=i_tot,
        iron_left=i_tot,
        dry_total=d_tot,
        dry_left=d_tot,
        steam_total=s_tot,
        steam_left=s_tot,
        service_items=dynamic_service_items
    )
    db.add(customer_pkg)
    db.commit()
    db.refresh(customer_pkg)
    
    # Record Order in Order History for Package Purchase
    try:
        from app.models.order import Order
        from app.models.order_item import OrderItem
        from app.models.customer import Customer
        
        # Ensure customer exists in customers table
        cust_rec = db.query(Customer).filter(
            Customer.id == payload.customer_id,
            Customer.tenant_id == current_user.tenant_id
        ).first()
        
        if not cust_rec:
            user_rec = db.query(User).filter(User.id == payload.customer_id).first()
            if user_rec:
                cust_rec = Customer(
                    id=user_rec.id,
                    tenant_id=current_user.tenant_id,
                    name=user_rec.name,
                    phone=user_rec.phone,
                    email=user_rec.email,
                    wallet_balance=Decimal("0.0"),
                    loyalty_points=0,
                    qr_secret=uuid.uuid4().hex
                )
                db.add(cust_rec)
                db.commit()

        if cust_rec:
            new_order_id = uuid.uuid4()
            now_time = datetime.datetime.utcnow()
            ord_num = f"ORD-PKG-{now_time.strftime('%Y%m%d')}-{str(new_order_id)[:4].upper()}"
            
            new_order = Order(
                id=new_order_id,
                tenant_id=current_user.tenant_id,
                customer_id=cust_rec.id,
                order_number=ord_num,
                status="COMPLETED",
                payment_status="PAID",
                total_amount=Decimal(str(final_price)),
                discount=Decimal(str(discount)),
                paid_amount=Decimal(str(final_price)),
                special_instructions=f"Purchased Prepaid Package: {pkg.name}",
                created_at=now_time,
                updated_at=now_time
            )
            db.add(new_order)
            db.commit()
    except Exception as e_ord:
        import logging
        logging.getLogger(__name__).error(f"Could not record order for package purchase: {e_ord}")
    
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
        db.refresh(customer_pkg)

    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger(__name__).error(f"Could not generate wallet pass for package {customer_pkg.id}: {e}")

    # 3. Trigger WhatsApp Notification
    if customer:
        try:
            WhatsAppService.send_package_activated_message(customer, customer_pkg)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to send WhatsApp notification for package {customer_pkg.id}: {e}")
        
    setattr(customer_pkg, "wallet_generation", wallet_status)
    return customer_pkg

from app.schemas.prepaid_package import CustomerPackageDeductRequest

@router.get("/customer/{customer_id}/active", response_model=CustomerPackageResponse)
def get_active_customer_package(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch the single active CustomerPackage record for a customer as the single source of truth"""
    target_user = None
    try:
        val_uuid = uuid.UUID(customer_id)
        target_user = db.query(User).filter(
            User.id == val_uuid,
            User.tenant_id == current_user.tenant_id
        ).first()
    except Exception:
        pass
        
    if not target_user:
        target_user = db.query(User).filter(
            User.tenant_id == current_user.tenant_id,
            (User.phone == customer_id) | (User.email == customer_id)
        ).first()

    real_customer_id = target_user.id if target_user else None
    if not real_customer_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    cp = db.query(CustomerPackage).options(joinedload(CustomerPackage.package)).filter(
        CustomerPackage.customer_id == real_customer_id,
        CustomerPackage.tenant_id == current_user.tenant_id,
        CustomerPackage.status.in_(["ACTIVE", "IN_USE"])
    ).order_by(CustomerPackage.purchase_date.desc()).first()

    if not cp:
        cp = db.query(CustomerPackage).options(joinedload(CustomerPackage.package)).filter(
            CustomerPackage.customer_id == real_customer_id,
            CustomerPackage.tenant_id == current_user.tenant_id
        ).order_by(CustomerPackage.purchase_date.desc()).first()

    if not cp:
        raise HTTPException(status_code=404, detail="No active package found for customer")

    # Auto-fix missing service_items for existing packages
    if cp and (not cp.service_items or len(cp.service_items) == 0):
        resolved = resolve_service_items_from_package(db, cp.package)
        if resolved:
            from sqlalchemy.orm.attributes import flag_modified
            cp.service_items = resolved
            flag_modified(cp, "service_items")
            db.commit()
            db.refresh(cp)

    return cp

@router.post("/deduct", response_model=CustomerPackageResponse)
def deduct_package_usage(
    payload: CustomerPackageDeductRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deduct package usage from CustomerPackage database record and trigger Apple Wallet OTA update"""
    cp = None
    if payload.customer_package_id:
        cp = db.query(CustomerPackage).options(joinedload(CustomerPackage.package)).filter(
            CustomerPackage.id == payload.customer_package_id,
            CustomerPackage.tenant_id == current_user.tenant_id
        ).first()

    if not cp and payload.customer_id:
        cp = db.query(CustomerPackage).options(joinedload(CustomerPackage.package)).filter(
            CustomerPackage.customer_id == payload.customer_id,
            CustomerPackage.tenant_id == current_user.tenant_id,
            CustomerPackage.status.in_(["ACTIVE", "IN_USE"])
        ).order_by(CustomerPackage.purchase_date.desc()).first()

    if not cp:
        raise HTTPException(status_code=404, detail="Active customer package not found")

    # --- Dynamic service_items deduction (primary path) ---
    current_items = list(cp.service_items or [])
    a_used = payload.amount_used or 0.0
    c_bal = float(cp.current_balance or 0.0)

    if a_used > c_bal:
        raise HTTPException(status_code=400, detail=f"Cannot deduct QR {a_used:.2f}. Wallet balance is QR {c_bal:.2f}.")

    # If dynamic deductions are provided, use them (primary path)
    if payload.deductions and len(payload.deductions) > 0:
        for ded in payload.deductions:
            if ded.quantity <= 0:
                continue
            # Find the matching service in service_items
            found = False
            for si in current_items:
                if si["service"].lower() == ded.service.lower():
                    found = True
                    if ded.quantity > si["left"]:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Cannot deduct {ded.quantity} {ded.service}. Only {si['left']} remaining."
                        )
                    si["left"] = max(0, si["left"] - ded.quantity)
                    break
            if not found:
                raise HTTPException(
                    status_code=400,
                    detail=f"Service '{ded.service}' not found in this customer's package."
                )
    else:
        # Legacy fixed-field deductions (backward compat)
        w_used = payload.wash_used or 0
        i_used = payload.iron_used or 0
        d_used = payload.dry_used or 0
        s_used = payload.steam_used or 0

        if w_used > 0 or i_used > 0 or d_used > 0 or s_used > 0:
            # Map legacy fields to service_items
            legacy_map = {
                "wash": w_used, "iron": i_used, "dry": d_used, "steam": s_used
            }
            for si in current_items:
                cat = si["service"].lower()
                deduct_qty = 0
                if ("wash" in cat or "fold" in cat) and legacy_map["wash"] > 0:
                    deduct_qty = legacy_map["wash"]
                    legacy_map["wash"] = 0
                elif ("press" in cat or "iron" in cat) and "steam" not in cat and legacy_map["iron"] > 0:
                    deduct_qty = legacy_map["iron"]
                    legacy_map["iron"] = 0
                elif ("dry" in cat or "premium" in cat) and legacy_map["dry"] > 0:
                    deduct_qty = legacy_map["dry"]
                    legacy_map["dry"] = 0
                elif "steam" in cat and legacy_map["steam"] > 0:
                    deduct_qty = legacy_map["steam"]
                    legacy_map["steam"] = 0

                if deduct_qty > 0:
                    if deduct_qty > si["left"]:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Cannot deduct {deduct_qty} {si['service']}. Only {si['left']} remaining."
                        )
                    si["left"] = max(0, si["left"] - deduct_qty)

    # Check if any deduction was actually made
    total_deducted = 0
    if payload.deductions and len(payload.deductions) > 0:
        total_deducted = sum(d.quantity for d in payload.deductions if d.quantity > 0)
    else:
        total_deducted = (payload.wash_used or 0) + (payload.iron_used or 0) + (payload.dry_used or 0) + (payload.steam_used or 0)

    if total_deducted <= 0 and a_used <= 0:
        raise HTTPException(status_code=400, detail="Please enter at least one deduction quantity or wallet amount.")

    # Persist updated service_items back
    from sqlalchemy.orm.attributes import flag_modified
    cp.service_items = current_items
    flag_modified(cp, "service_items")

    # Sync legacy fixed columns from service_items
    w_left, i_left, d_left, s_left = 0, 0, 0, 0
    w_tot, i_tot, d_tot, s_tot = 0, 0, 0, 0
    for si in current_items:
        cat = si["service"].lower()
        if "steam" in cat:
            s_left += si["left"]; s_tot += si["total"]
        elif "wash" in cat or "fold" in cat:
            w_left += si["left"]; w_tot += si["total"]
        elif ("press" in cat or "iron" in cat):
            i_left += si["left"]; i_tot += si["total"]
        elif "dry" in cat or "premium" in cat:
            d_left += si["left"]; d_tot += si["total"]
        else:
            w_left += si["left"]; w_tot += si["total"]

    cp.wash_left = w_left; cp.wash_total = w_tot
    cp.iron_left = i_left; cp.iron_total = i_tot
    cp.dry_left = d_left; cp.dry_total = d_tot
    cp.steam_left = s_left; cp.steam_total = s_tot

    # Deduct wallet amount
    cp.current_balance = max(0.0, c_bal - a_used)
    cp.used_amount = float(cp.used_amount or 0.0) + a_used

    # Determine status
    total_left = sum(si["left"] for si in current_items)
    if total_left <= 0:
        cp.status = "COMPLETED"
        cp.pass_color = "WHITE"
    else:
        cp.status = "IN_USE"
        cp.pass_color = "GREY"

    db.commit()
    db.refresh(cp)

    # Record PackageUsageHistory audit tracking
    try:
        deducted_summary = []
        if payload.deductions:
            for d in payload.deductions:
                if d.quantity > 0:
                    deducted_summary.append(f"{d.quantity}x {d.service}")
        if a_used > 0:
            deducted_summary.append(f"QR {a_used:.2f} Wallet")
            
        desc_str = ", ".join(deducted_summary) if deducted_summary else "Package Deduction"
        
        audit_hist = PackageUsageHistory(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            customer_package_id=cp.id,
            quantity_used=total_deducted,
            remarks=payload.remarks or desc_str,
            transaction_date=datetime.datetime.utcnow()
        )
        db.add(audit_hist)
        db.commit()
    except Exception as e_hist:
        import logging
        logging.getLogger(__name__).error(f"Error logging PackageUsageHistory: {e_hist}")

    # Regenerate Pass & APNs push
    customer = db.query(User).filter(User.id == cp.customer_id).first()
    try:
        import logging
        pkg_logger = logging.getLogger(__name__)
        pkg_logger.warning("[DEBUG] ABOUT TO CALL update_wallet_pass_on_usage package_id=%s", cp.id)
        WalletService.update_wallet_pass_on_usage(db, cp, customer)
        pkg_logger.warning("[DEBUG] RETURNED FROM update_wallet_pass_on_usage package_id=%s", cp.id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"Error updating wallet pass on usage: {e}")

    return cp

@router.get("/customer-packages/all", response_model=List[CustomerPackageResponse])
def get_all_tenant_customer_packages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all purchased CustomerPackage records for the current tenant"""
    pkgs = db.query(CustomerPackage).options(
        joinedload(CustomerPackage.package),
        joinedload(CustomerPackage.customer)
    ).filter(
        CustomerPackage.tenant_id == current_user.tenant_id
    ).order_by(CustomerPackage.purchase_date.desc()).all()
    return pkgs

@router.get("/customer/{customer_id}", response_model=List[CustomerPackageResponse])
def get_customer_packages(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all purchased packages for a specific customer by UUID, phone, or referral code"""
    target_user = None
    try:
        val_uuid = uuid.UUID(customer_id)
        target_user = db.query(User).filter(
            User.id == val_uuid,
            User.tenant_id == current_user.tenant_id
        ).first()
    except Exception:
        pass
        
    if not target_user:
        target_user = db.query(User).filter(
            User.tenant_id == current_user.tenant_id,
            (User.phone == customer_id) | (User.email == customer_id)
        ).first()

    if not target_user:
        from app.models.customer import Customer
        cust_rec = db.query(Customer).filter(
            Customer.tenant_id == current_user.tenant_id,
            (Customer.referral_code == customer_id) | (Customer.phone == customer_id)
        ).first()
        if cust_rec:
            target_user = db.query(User).filter(User.id == cust_rec.id).first()

    real_customer_id = target_user.id if target_user else None
    if not real_customer_id:
        return []

    pkgs = db.query(CustomerPackage).options(joinedload(CustomerPackage.package)).filter(
        CustomerPackage.customer_id == real_customer_id,
        CustomerPackage.tenant_id == current_user.tenant_id
    ).order_by(CustomerPackage.purchase_date.desc()).all()
    
    # Auto-update status for expired ones & generate missing wallet URLs before returning
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
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

            if not p.apple_wallet_url and target_user:
                try:
                    WalletService.create_and_save_wallet_pass(
                        db=db,
                        package=p,
                        customer=target_user,
                        company_name=company_name
                    )
                    db.refresh(p)
                except Exception as e:
                    import traceback
                    print(f"Could not generate wallet pass on the fly: {e}")
                    print(traceback.format_exc())

            if not p.apple_wallet_url and p.secure_token:
                p.apple_wallet_url = f"/api/v1/wallet/apple/pass/{p.secure_token}"

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
