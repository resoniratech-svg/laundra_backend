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

@router.get("/pass/{secure_token}")
def download_apple_pass(
    secure_token: str,
    db: Session = Depends(get_db)
):
    """
    Downloads the generated .pkpass file.
    Publicly accessible via secure_token, package_id, or serial_number.
    """
    from app.models.customer_package import CustomerPackage
    from app.models.user import User

    # Clean the secure_token parameter in case it includes prefix/suffix
    clean_token = secure_token
    if clean_token.startswith("package_"):
        clean_token = clean_token[len("package_"):]
    if clean_token.endswith(".pkpass"):
        clean_token = clean_token[:-len(".pkpass")]

    # Look up by secure_token, package ID, or serial number
    package = db.query(CustomerPackage).filter(
        (CustomerPackage.secure_token == clean_token) |
        (CustomerPackage.secure_token.like(f"{clean_token}%"))
    ).first()
    if not package:
        try:
            val_uuid = UUID(clean_token)
            package = db.query(CustomerPackage).filter(CustomerPackage.id == val_uuid).first()
        except Exception:
            pass

    if not package:
        pass_rec_search = db.query(WalletPass).filter(
            (WalletPass.serial_number == clean_token) |
            (WalletPass.apple_serial_number == clean_token) |
            (WalletPass.authentication_token == clean_token) |
            (WalletPass.serial_number.like(f"%{clean_token}%")) |
            (WalletPass.apple_serial_number.like(f"%{clean_token}%"))
        ).first()
        if pass_rec_search:
            package = db.query(CustomerPackage).filter(CustomerPackage.id == pass_rec_search.customer_package_id).first()

    if not package:
        raise HTTPException(status_code=404, detail="Apple Wallet pass not found")

    # Auto-regenerate .pkpass file before serving to guarantee it has latest balances and theme!
    customer = db.query(User).filter(User.id == package.customer_id).first()
    try:
        WalletService.update_wallet_pass_on_usage(db, package, customer)
    except Exception as e:
        logger.warning(f"Could not auto-refresh pass before download: {e}")

    pass_rec = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
    if not pass_rec:
        try:
            logger.info(f"WalletPass missing for package {package.id}. Generating on-the-fly.")
            WalletService.create_and_save_wallet_pass(db, package, customer)
            db.commit()
            pass_rec = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
        except Exception as ex:
            logger.error(f"Failed to generate missing WalletPass on-the-fly: {ex}")

    if not pass_rec or not pass_rec.pass_file_path:
        raise HTTPException(status_code=404, detail="Apple Wallet pass file not found")

    file_path = Path(pass_rec.pass_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Pass file missing on server disk")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.apple.pkpass",
        filename="package.pkpass"
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

# =====================================================================
# OFFICIAL APPLE PASSKIT WEB SERVICE REST API ENDPOINTS
# =====================================================================

from typing import Dict, Any, Optional
import datetime
from fastapi import Header, Response
from app.models.apple_device_registration import AppleDeviceRegistration

@router.post("/v1/devices/{device_library_identifier}/registrations/{pass_type_identifier}/{serial_number}", status_code=status.HTTP_201_CREATED)
def register_passkit_device(
    device_library_identifier: str,
    pass_type_identifier: str,
    serial_number: str,
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Endpoint 1: Register Device
    Validates ApplePass auth token and registers an iOS device for push notifications.
    """
    auth_token = (authorization or "").replace("ApplePass ", "").strip()
    pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == serial_number).first()
    if not pass_rec or (pass_rec.authentication_token and pass_rec.authentication_token != auth_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    push_token = payload.get("pushToken")
    if not push_token:
        raise HTTPException(status_code=400, detail="Missing pushToken")

    reg = db.query(AppleDeviceRegistration).filter(
        AppleDeviceRegistration.device_library_identifier == device_library_identifier,
        AppleDeviceRegistration.serial_number == serial_number
    ).first()

    if not reg:
        reg = AppleDeviceRegistration(
            device_library_identifier=device_library_identifier,
            push_token=push_token,
            pass_type_identifier=pass_type_identifier,
            serial_number=serial_number,
            wallet_pass_id=pass_rec.id
        )
        db.add(reg)
    else:
        reg.push_token = push_token

    db.commit()
    return {"status": "registered"}

@router.delete("/v1/devices/{device_library_identifier}/registrations/{pass_type_identifier}/{serial_number}")
def unregister_passkit_device(
    device_library_identifier: str,
    pass_type_identifier: str,
    serial_number: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Endpoint 2: Unregister Device
    Removes device registration when a pass is removed from Apple Wallet.
    """
    auth_token = (authorization or "").replace("ApplePass ", "").strip()
    pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == serial_number).first()
    if not pass_rec or (pass_rec.authentication_token and pass_rec.authentication_token != auth_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    reg = db.query(AppleDeviceRegistration).filter(
        AppleDeviceRegistration.device_library_identifier == device_library_identifier,
        AppleDeviceRegistration.serial_number == serial_number
    ).first()

    if reg:
        db.delete(reg)
        db.commit()

    return {"status": "unregistered"}

@router.get("/v1/devices/{device_library_identifier}/registrations/{pass_type_identifier}")
def check_updated_passes(
    device_library_identifier: str,
    pass_type_identifier: str,
    passesUpdatedSince: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Endpoint 3: Check Updated Passes
    Apple Wallet calls this after receiving a push notification to fetch updated serial numbers.
    """
    regs = db.query(AppleDeviceRegistration).filter(
        AppleDeviceRegistration.device_library_identifier == device_library_identifier,
        AppleDeviceRegistration.pass_type_identifier == pass_type_identifier
    ).all()

    if not regs:
        return Response(status_code=204)

    serial_numbers = [r.serial_number for r in regs if r.serial_number]
    last_updated_tag = str(int(datetime.datetime.utcnow().timestamp()))

    return {
        "lastUpdated": last_updated_tag,
        "serialNumbers": serial_numbers
    }

@router.get("/v1/passes/{pass_type_identifier}/{serial_number}")
def download_updated_passkit_pass(
    pass_type_identifier: str,
    serial_number: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Endpoint 4: Download Updated Pass
    Serves the latest signed .pkpass bundle directly to Apple Wallet over the air.
    """
    auth_token = (authorization or "").replace("ApplePass ", "").strip()
    pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == serial_number).first()
    if not pass_rec or (pass_rec.authentication_token and pass_rec.authentication_token != auth_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not pass_rec.pass_file_path or not Path(pass_rec.pass_file_path).exists():
        raise HTTPException(status_code=404, detail="Pass file missing")

    return FileResponse(
        path=Path(pass_rec.pass_file_path),
        media_type="application/vnd.apple.pkpass",
        filename=f"pass_{serial_number}.pkpass"
    )

@router.post("/v1/log")
def log_passkit_client_messages(
    payload: Dict[str, Any]
):
    """
    Endpoint 5: Apple Wallet Log Endpoint
    Receives sync logs/messages from iOS Apple Wallet client.
    """
    logs = payload.get("logs", [])
    for msg in logs:
        logger.info(f"[PassKit Client Log]: {msg}")
    return {"status": "logged"}
