import logging
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.wallet_pass import WalletPass
from app.schemas.apple_wallet import PassGenerationRequest, PassGenerationResponse
from app.services.wallet_service import WalletService
from app.services.apple_wallet.validation_service import ValidationService

logger = logging.getLogger("apple_wallet.api")

router = APIRouter(
    prefix="/wallet/apple",
    tags=["Apple Wallet"],
)

@router.post("/generate", response_model=PassGenerationResponse)
def generate_apple_pass(
    req: PassGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates a signed Apple Wallet .pkpass file for a customer package or order.
    Enforces multi-tenant isolation via current_user.tenant_id.
    """
    try:
        res = WalletService.generate_real_apple_wallet_pass(
            db=db,
            tenant_id=current_user.tenant_id,
            customer_id=req.customer_id,
            customer_name=req.customer_name,
            package_name=req.package_name,
            remaining_balance=req.remaining_balance,
            expiry_date=req.expiry_date,
            order_id=req.order_id
        )
        return PassGenerationResponse(
            success=True,
            serial_number=res["serial_number"],
            pass_id=res["pass_id"],
            download_url=res["download_url"],
            file_path=res["file_path"]
        )
    except Exception as e:
        logger.error(f"Failed to generate Apple Wallet pass: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Apple Wallet pass: {str(e)}"
        )

@router.get("/pass/{pass_id}")
def download_apple_pass(
    pass_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Downloads the generated .pkpass file.
    Enforces tenant access check.
    """
    pass_rec = db.query(WalletPass).filter(
        WalletPass.id == pass_id,
        WalletPass.tenant_id == current_user.tenant_id
    ).first()

    if not pass_rec or not pass_rec.pass_file_path:
        raise HTTPException(status_code=404, detail="Apple Wallet pass not found")

    file_path = Path(pass_rec.pass_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Pass file missing on server disk")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.apple.pkpass",
        filename=file_path.name
    )

@router.get("/validate")
def validate_apple_wallet_engine(
    current_user: User = Depends(get_current_user)
):
    """
    Validates Apple Wallet certificates, manifest hashing, signature pipeline, and engine settings.
    """
    val_svc = ValidationService()
    report = val_svc.validate_all()
    return report

@router.delete("/pass/{pass_id}")
def revoke_apple_pass(
    pass_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revokes an Apple Wallet pass.
    """
    pass_rec = db.query(WalletPass).filter(
        WalletPass.id == pass_id,
        WalletPass.tenant_id == current_user.tenant_id
    ).first()

    if not pass_rec:
        raise HTTPException(status_code=404, detail="Pass not found")

    pass_rec.status = "REVOKED"
    db.commit()
    return {"success": True, "message": "Apple Wallet pass revoked"}
