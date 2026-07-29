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
    Publicly accessible via secure_token, package_id, wallet_pass_id, or serial_number.
    Uses centralized WalletService.resolve_wallet_pass(db, identifier=...)
    """
    from app.models.customer_package import CustomerPackage
    from app.models.user import User
    from app.services.apple_wallet.telemetry import TraceContext, WalletLogger

    ctx = TraceContext()
    WalletLogger.log("info", "Apple Download", "START Web Download", ctx, identifier=secure_token)

    # Centralized resolution for any generic identifier
    pass_rec = WalletService.resolve_wallet_pass(
        db=db,
        identifier=secure_token
    )

    if not pass_rec:
        WalletLogger.log("error", "Apple Download", "FAILURE Web Download", ctx, identifier=secure_token, error="Pass not found")
        raise HTTPException(status_code=404, detail="Apple Wallet pass not found")

    # Auto-regenerate .pkpass file before serving to guarantee it has latest balances and theme!
    package = None
    if pass_rec.customer_package_id:
        package = db.query(CustomerPackage).filter(CustomerPackage.id == pass_rec.customer_package_id).first()
    if not package and pass_rec.customer_id:
        package = db.query(CustomerPackage).filter(
            CustomerPackage.customer_id == pass_rec.customer_id,
            CustomerPackage.status.in_(["ACTIVE", "IN_USE"])
        ).order_by(CustomerPackage.purchase_date.desc()).first()

    if package:
        customer = db.query(User).filter(User.id == package.customer_id).first()
        try:
            WalletService.update_wallet_pass_on_usage(db, package, customer, ctx=ctx)
            # Re-resolve after regeneration
            pass_rec = WalletService.resolve_wallet_pass(db=db, identifier=secure_token) or pass_rec
        except Exception as e:
            logger.warning(f"Could not auto-refresh pass before download: {e}")

    if not pass_rec or not pass_rec.pass_file_path:
        WalletLogger.log("error", "Apple Download", "FAILURE Web Download", ctx, identifier=secure_token, error="Pass file path missing")
        raise HTTPException(status_code=404, detail="Apple Wallet pass file not found")

    file_path = Path(pass_rec.pass_file_path)
    if not file_path.exists():
        WalletLogger.log("error", "Apple Download", "FAILURE Web Download", ctx, identifier=secure_token, error="Pass file missing on disk")
        raise HTTPException(status_code=404, detail="Pass file missing on server disk")

    download_name = f"pass_{pass_rec.serial_number or secure_token[:8]}.pkpass"
    f_size = file_path.stat().st_size if file_path.exists() else 0

    WalletLogger.log(
        "info", "Apple Download", "SUCCESS Web Download", ctx,
        serial_number=pass_rec.serial_number,
        file_path=str(file_path),
        size=f"{f_size} bytes"
    )

    return FileResponse(
        path=file_path,
        media_type="application/vnd.apple.pkpass",
        filename=download_name
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
import json
from fastapi import Header, Response
from app.models.apple_device_registration import AppleDeviceRegistration

@router.post("/v1/devices/{device_library_identifier}/registrations/{pass_type_identifier}/{serial_number}")
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
    Per Apple spec: returns HTTP 201 Created for new registrations, HTTP 200 OK for existing registrations.
    """
    from app.services.apple_wallet.telemetry import TraceContext, WalletLogger
    ctx = TraceContext()

    WalletLogger.log("info", "Device Reg", "START Register", ctx, device_id=device_library_identifier, serial_number=serial_number)

    auth_token = (authorization or "").replace("ApplePass ", "").strip()
    pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == serial_number).first()
    if not pass_rec or (pass_rec.authentication_token and pass_rec.authentication_token != auth_token):
        WalletLogger.log("error", "Device Reg", "FAILURE Register Auth Failed", ctx, device_id=device_library_identifier, serial_number=serial_number)
        raise HTTPException(status_code=401, detail="Unauthorized")

    push_token = payload.get("pushToken")
    if not push_token:
        WalletLogger.log("error", "Device Reg", "FAILURE Missing pushToken", ctx, device_id=device_library_identifier, serial_number=serial_number)
        raise HTTPException(status_code=400, detail="Missing pushToken")

    reg = db.query(AppleDeviceRegistration).filter(
        AppleDeviceRegistration.device_library_identifier == device_library_identifier,
        AppleDeviceRegistration.serial_number == serial_number
    ).first()

    is_new = False
    if not reg:
        reg = AppleDeviceRegistration(
            device_library_identifier=device_library_identifier,
            push_token=push_token,
            pass_type_identifier=pass_type_identifier,
            serial_number=serial_number,
            wallet_pass_id=pass_rec.id
        )
        db.add(reg)
        is_new = True
    else:
        reg.push_token = push_token

    db.commit()

    WalletLogger.log(
        "info", "Device Reg", "SUCCESS Registered", ctx,
        device_id=device_library_identifier,
        serial_number=serial_number,
        push_token=WalletLogger.mask(push_token),
        is_new=is_new
    )

    status_code = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
    return Response(
        status_code=status_code,
        content=json.dumps({"status": "registered"}),
        media_type="application/json"
    )

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
    from app.services.apple_wallet.telemetry import TraceContext, WalletLogger
    ctx = TraceContext()
    WalletLogger.log("info", "Device Reg", "START Unregister", ctx, device_id=device_library_identifier, serial_number=serial_number)

    auth_token = (authorization or "").replace("ApplePass ", "").strip()
    pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == serial_number).first()
    if not pass_rec or (pass_rec.authentication_token and pass_rec.authentication_token != auth_token):
        WalletLogger.log("error", "Device Reg", "FAILURE Unregister Auth Failed", ctx, device_id=device_library_identifier, serial_number=serial_number)
        raise HTTPException(status_code=401, detail="Unauthorized")

    reg = db.query(AppleDeviceRegistration).filter(
        AppleDeviceRegistration.device_library_identifier == device_library_identifier,
        AppleDeviceRegistration.serial_number == serial_number
    ).first()

    if reg:
        db.delete(reg)
        db.commit()

    WalletLogger.log("info", "Device Reg", "SUCCESS Unregistered", ctx, device_id=device_library_identifier, serial_number=serial_number)
    return {"status": "unregistered"}

import time

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
    Per Apple spec: filters by passesUpdatedSince tag and returns HTTP 204 if no passes were updated.
    """
    from app.services.apple_wallet.telemetry import TraceContext, WalletLogger
    ctx = TraceContext()

    WalletLogger.log(
        "info", "Apple Polling", "START GET /devices", ctx,
        device_id=device_library_identifier,
        pass_type=pass_type_identifier,
        passesUpdatedSince=passesUpdatedSince
    )

    regs = db.query(AppleDeviceRegistration).filter(
        AppleDeviceRegistration.device_library_identifier == device_library_identifier,
        AppleDeviceRegistration.pass_type_identifier == pass_type_identifier
    ).all()

    if not regs:
        WalletLogger.log("info", "Apple Polling", "SUCCESS GET /devices", ctx, status="204 No Registrations")
        return Response(status_code=204)

    since_ts = 0
    if passesUpdatedSince:
        try:
            since_ts = int(passesUpdatedSince)
        except Exception:
            since_ts = 0

    updated_serials = []
    max_updated_ts = 0

    for r in regs:
        pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == r.serial_number).first()
        if pass_rec:
            raw_updated_at = getattr(pass_rec, 'updated_at', None)
            raw_created_at = getattr(pass_rec, 'created_at', None)
            updated_dt = raw_updated_at or raw_created_at or datetime.datetime.utcnow()
            pass_ts = int(updated_dt.timestamp() * 1_000_000)
            if pass_ts > max_updated_ts:
                max_updated_ts = pass_ts

            is_greater = pass_ts > since_ts
            WalletLogger.log(
                "info", "Apple Polling", "Comparison", ctx,
                serial_number=r.serial_number,
                server_updated_at=raw_updated_at,
                pass_ts=pass_ts,
                since_ts=since_ts,
                is_greater=is_greater
            )

            if is_greater:
                updated_serials.append(r.serial_number)
        else:
            updated_serials.append(r.serial_number)

    last_updated_tag = str(max_updated_ts if max_updated_ts > 0 else int(datetime.datetime.utcnow().timestamp() * 1_000_000))

    if passesUpdatedSince and not updated_serials:
        WalletLogger.log(
            "info", "Apple Polling", "SUCCESS GET /devices", ctx,
            status="204 No Content",
            lastUpdated=last_updated_tag
        )
        return Response(status_code=204)

    WalletLogger.log(
        "info", "Apple Polling", "SUCCESS GET /devices", ctx,
        status="200 OK",
        serialNumbers=updated_serials,
        lastUpdated=last_updated_tag
    )

    return {
        "lastUpdated": last_updated_tag,
        "serialNumbers": updated_serials
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
    Optimized: Serves existing file directly without redundant regeneration unless file is missing.
    """
    from app.services.apple_wallet.telemetry import TraceContext, WalletLogger
    ctx = TraceContext()

    WalletLogger.log(
        "info", "Apple Download", "START GET /passes", ctx,
        serial_number=serial_number,
        pass_type=pass_type_identifier
    )

    auth_token = (authorization or "").replace("ApplePass ", "").strip()
    pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == serial_number).first()

    if not pass_rec or (pass_rec.authentication_token and pass_rec.authentication_token != auth_token):
        WalletLogger.log("error", "Apple Download", "FAILURE GET /passes Unauthorized", ctx, serial_number=serial_number)
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Only regenerate if file is missing on server disk
    if not pass_rec.pass_file_path or not Path(pass_rec.pass_file_path).exists():
        if pass_rec.customer_package_id:
            from app.models.customer_package import CustomerPackage
            from app.models.user import User
            cp = db.query(CustomerPackage).filter(CustomerPackage.id == pass_rec.customer_package_id).first()
            if cp:
                cust = db.query(User).filter(User.id == cp.customer_id).first()
                try:
                    WalletService.update_wallet_pass_on_usage(db, cp, cust, ctx=ctx)
                    db.refresh(pass_rec)
                except Exception as e:
                    logger.warning(f"Could not regenerate pass before PassKit download: {e}")

    file_path = Path(pass_rec.pass_file_path) if pass_rec.pass_file_path else None
    file_exists = file_path.exists() if file_path else False
    file_size = file_path.stat().st_size if (file_exists and file_path) else 0

    if not file_exists:
        WalletLogger.log("error", "Apple Download", "FAILURE GET /passes File Missing", ctx, serial_number=serial_number)
        raise HTTPException(status_code=404, detail="Pass file missing")

    WalletLogger.log(
        "info", "Apple Download", "SUCCESS GET /passes", ctx,
        serial_number=serial_number,
        file_path=str(file_path),
        size=f"{file_size} bytes"
    )

    return FileResponse(
        path=file_path,
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
    print("ENTER log_passkit_client_messages", flush=True)
    logger.warning("ENTER log_passkit_client_messages")
    logs = payload.get("logs", [])
    for msg in logs:
        log_line = f"[PassKit Client Log]: {msg}"
        logger.warning(log_line)
        print(log_line, flush=True)
    return {"status": "logged"}
