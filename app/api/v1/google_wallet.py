import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.models.company import Company
from app.services.google_wallet.pass_service import GoogleWalletPassService

logger = logging.getLogger("google_wallet.api")

router = APIRouter(
    prefix="/wallet/google",
    tags=["Google Wallet"],
)

@router.get("/pass/{token_or_id:path}")
def get_google_wallet_pass_redirect(
    token_or_id: str,
    db: Session = Depends(get_db)
):
    """
    Clean redirect endpoint for Google Wallet passes:
    GET /api/v1/wallet/google/pass/{customer_package_id_or_secure_token}
    
    Validates package identifier, fetches/reuses the Google Wallet GenericObject,
    generates a fresh signed Save-to-Google-Wallet JWT URL, and performs an HTTP 307 Redirect.
    """
    clean_token = token_or_id.replace("customer/", "").strip()
    pkg = None

    # 1. Try matching secure_token
    pkg = db.query(CustomerPackage).filter(CustomerPackage.secure_token == clean_token).first()

    # 2. Try matching UUID package ID
    if not pkg:
        try:
            val_uuid = UUID(clean_token)
            pkg = db.query(CustomerPackage).filter(CustomerPackage.id == val_uuid).first()
        except Exception:
            pass

    # 3. Try matching Customer ID (UUID)
    if not pkg:
        try:
            c_uuid = UUID(clean_token)
            pkg = db.query(CustomerPackage).filter(
                CustomerPackage.customer_id == c_uuid,
                CustomerPackage.status.in_(["ACTIVE", "IN_USE"])
            ).order_by(CustomerPackage.purchase_date.desc()).first()
            if not pkg:
                pkg = db.query(CustomerPackage).filter(
                    CustomerPackage.customer_id == c_uuid
                ).order_by(CustomerPackage.purchase_date.desc()).first()
        except Exception:
            pass

    # 4. Centralized WalletPass lookup fallback
    if not pkg:
        from app.services.wallet_service import WalletService
        wp = WalletService.resolve_wallet_pass(db, identifier=clean_token)
        if wp:
            if wp.customer_package_id:
                pkg = db.query(CustomerPackage).filter(CustomerPackage.id == wp.customer_package_id).first()
            if not pkg and wp.customer_id:
                pkg = db.query(CustomerPackage).filter(
                    CustomerPackage.customer_id == wp.customer_id,
                    CustomerPackage.status.in_(["ACTIVE", "IN_USE"])
                ).order_by(CustomerPackage.purchase_date.desc()).first()

    if not pkg:
        logger.warning(f"[GoogleWallet API] CustomerPackage not found for identifier: {token_or_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prepaid package pass not found"
        )

    customer = db.query(User).filter(User.id == pkg.customer_id).first()
    company = db.query(Company).filter(Company.id == pkg.tenant_id).first()

    try:
        res = GoogleWalletPassService.generate_google_wallet_pass(
            db=db,
            package=pkg,
            customer=customer,
            company=company
        )
        if not res.get("success"):
            err_msg = res.get("error") or "Google Wallet pass URL generation failed"
            logger.error(f"[GoogleWallet API] Pass generation error for package {pkg.id}: {err_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Google Wallet pass generation failed: {err_msg}"
            )

        save_url = res.get("raw_save_url") or res.get("google_wallet_url")
        if save_url and save_url.startswith("http"):
            logger.info(f"[GoogleWallet API] Successfully redirecting package {pkg.id} to Google Wallet Save URL")
            return RedirectResponse(url=save_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        
        logger.error(f"[GoogleWallet API] Failed to generate valid Save URL for package {pkg.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Wallet pass URL generation failed"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GoogleWallet API] Error generating Google Wallet pass for {token_or_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error accessing Google Wallet pass: {str(e)}"
        )
