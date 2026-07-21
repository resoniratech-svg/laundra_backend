from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import time

from app.core.database import get_db
from app.dependencies import get_current_admin, get_current_user
from app.models.wallet_pass import WalletPass
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.wallet.client import test_wallet_authentication
from app.wallet.class_service import create_or_get_generic_class
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallet", tags=["Google Wallet Management"])

@router.get(
    "/health",
    summary="Google Wallet Service Health Check",
    description="Verifies Google OAuth2 authentication, configuration validity, and API reachability."
)
def wallet_health_check():
    """
    Phase 15 Step 3: Health Check Endpoint
    """
    start_time = time.time()
    try:
        auth_res = test_wallet_authentication()
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "HEALTHY",
            "message": "Google Wallet API integration is healthy and authenticated.",
            "authentication": "OK",
            "service_account": auth_res.get("service_account_email"),
            "project_id": auth_res.get("project_id"),
            "api_latency_ms": latency_ms
        }
    except Exception as e:
        return {
            "status": "UNHEALTHY",
            "message": f"Google Wallet authentication or health check failed: {str(e)}",
            "authentication": "FAILED"
        }

@router.get(
    "/class",
    summary="Create or Verify Generic Wallet Class",
    description="Ensures the master Generic Class (338800000023177180.laundry_package) exists."
)
def get_or_create_wallet_class():
    try:
        result = create_or_get_generic_class()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Google Wallet Generic Class: {str(e)}"
        )

@router.get(
    "/admin/customer/{customer_id}",
    summary="Search Customer Wallet Passes",
    description="Retrieve all Google Wallet passes associated with a specific customer ID."
)
def search_customer_wallets(
    customer_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    passes = db.query(WalletPass).filter(
        WalletPass.customer_id == customer_id,
        WalletPass.company_id == current_admin.tenant_id
    ).all()
    
    return [
        {
            "id": str(p.id),
            "customer_package_id": str(p.customer_package_id),
            "class_id": p.class_id,
            "object_id": p.wallet_object_id,
            "wallet_url": p.wallet_url,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        }
        for p in passes
    ]

@router.post(
    "/admin/regenerate-link/{customer_package_id}",
    summary="Regenerate Add to Google Wallet Link",
    description="Forces regeneration of a fresh signed Google Wallet Save URL for a customer package."
)
def regenerate_wallet_link(
    customer_package_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    pkg = db.query(CustomerPackage).filter(
        CustomerPackage.id == customer_package_id,
        CustomerPackage.tenant_id == current_admin.tenant_id
    ).first()
    
    if not pkg:
        raise HTTPException(status_code=404, detail="Customer package not found")
        
    customer = db.query(User).filter(User.id == pkg.customer_id).first()
    company_name = getattr(current_admin, 'company', None).name if getattr(current_admin, 'company', None) else "Laundra Laundry"
    
    wallet_pass = WalletService.create_and_save_wallet_pass(
        db=db,
        package=pkg,
        customer=customer,
        company_name=company_name
    )
    
    return {
        "success": True,
        "customer_package_id": str(pkg.id),
        "google_wallet_url": pkg.google_wallet_url,
        "object_id": wallet_pass.object_id if wallet_pass else None
    }

@router.post(
    "/admin/force-update/{customer_package_id}",
    summary="Force Update Wallet Pass",
    description="Forces a sync update of the Google Wallet pass data with current database state."
)
def force_update_wallet_pass(
    customer_package_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    pkg = db.query(CustomerPackage).filter(
        CustomerPackage.id == customer_package_id,
        CustomerPackage.tenant_id == current_admin.tenant_id
    ).first()
    
    if not pkg:
        raise HTTPException(status_code=404, detail="Customer package not found")
        
    customer = db.query(User).filter(User.id == pkg.customer_id).first()
    WalletService.update_wallet_pass_on_usage(db=db, package=pkg, customer=customer)
    
    return {
        "success": True,
        "message": f"Wallet pass for package {customer_package_id} updated successfully.",
        "current_balance": float(pkg.current_balance or 0.0),
        "used_quantity": pkg.used_quantity,
        "status": pkg.status
    }

@router.get(
    "/admin/metrics",
    summary="Google Wallet Monitoring Metrics",
    description="Provides real-time telemetry metrics on total passes, active passes, and utilization."
)
def get_wallet_metrics(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    total = db.query(WalletPass).filter(WalletPass.company_id == current_admin.tenant_id).count()
    active = db.query(WalletPass).filter(WalletPass.company_id == current_admin.tenant_id, WalletPass.status == "ACTIVE").count()
    fully_utilized = db.query(WalletPass).filter(WalletPass.company_id == current_admin.tenant_id, WalletPass.status == "FULLY_UTILIZED").count()
    expired = db.query(WalletPass).filter(WalletPass.company_id == current_admin.tenant_id, WalletPass.status == "EXPIRED").count()
    
    return {
        "metrics": {
            "total_wallets_created": total,
            "active_wallets": active,
            "fully_utilized_wallets": fully_utilized,
            "expired_wallets": expired,
            "failed_creations": 0,
            "failed_updates": 0
        }
    }
