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

    # Centralized resolution for any generic identifier
    pass_rec = WalletService.resolve_wallet_pass(
        db=db,
        identifier=secure_token
    )

    if not pass_rec:
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
            WalletService.update_wallet_pass_on_usage(db, package, customer)
            # Re-resolve after regeneration
            pass_rec = WalletService.resolve_wallet_pass(db=db, identifier=secure_token) or pass_rec
        except Exception as e:
            logger.warning(f"Could not auto-refresh pass before download: {e}")

    if not pass_rec or not pass_rec.pass_file_path:
        raise HTTPException(status_code=404, detail="Apple Wallet pass file not found")

    file_path = Path(pass_rec.pass_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Pass file missing on server disk")

    download_name = f"pass_{pass_rec.serial_number or secure_token[:8]}.pkpass"

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
    print("ENTER register_passkit_device", flush=True)
    logger.warning("ENTER register_passkit_device")
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

    logger.info(f"[OTA Lifecycle] Device registered for push updates: device_id={device_library_identifier}, serial={serial_number}, is_new={is_new}")

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
    print("ENTER unregister_passkit_device", flush=True)
    logger.warning("ENTER unregister_passkit_device")
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
    print("ENTER check_updated_passes", flush=True)
    logger.warning("ENTER check_updated_passes")
    start_time = time.time()
    entry_msg = (
        f"[OTA LOGS] ENTRY GET /devices | device_id={device_library_identifier} | "
        f"pass_type={pass_type_identifier} | passesUpdatedSince={passesUpdatedSince}"
    )
    logger.warning(entry_msg)
    print(entry_msg, flush=True)

    regs = db.query(AppleDeviceRegistration).filter(
        AppleDeviceRegistration.device_library_identifier == device_library_identifier,
        AppleDeviceRegistration.pass_type_identifier == pass_type_identifier
    ).all()

    reg_count = len(regs)
    logger.warning(f"[OTA LOGS] Registrations found: count={reg_count}")
    print(f"[OTA LOGS] Registrations found: count={reg_count}", flush=True)

    if not regs:
        duration_ms = (time.time() - start_time) * 1000
        exit_msg = f"[OTA LOGS] EXIT GET /devices | Status: 204 (No Registrations) | Duration: {duration_ms:.2f}ms"
        logger.warning(exit_msg)
        print(exit_msg, flush=True)
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

            file_path_str = getattr(pass_rec, 'pass_file_path', None)
            file_path = Path(file_path_str) if file_path_str else None
            file_exists = file_path.exists() if file_path else False
            file_mtime_dt = None
            file_mtime_ts = None
            if file_exists:
                mtime_sec = file_path.stat().st_mtime
                file_mtime_ts = int(mtime_sec * 1_000_000)
                file_mtime_dt = datetime.datetime.utcfromtimestamp(mtime_sec).isoformat()

            diag_msg = (
                "------------------------------------\n"
                "[CHECK_UPDATED_PASSES DIAGNOSTIC]\n"
                f"WalletPass ID: {pass_rec.id}\n"
                f"Serial Number: {r.serial_number}\n"
                f"updated_at (raw datetime): {raw_updated_at}\n"
                f"created_at (raw datetime): {raw_created_at}\n"
                f"pass_ts (microsecond): {pass_ts}\n"
                f"passesUpdatedSince (raw query parameter): {passesUpdatedSince}\n"
                f"since_ts (microsecond): {since_ts}\n"
                f"Comparison: pass_ts > since_ts ? -> {is_greater}\n"
                f"Pass file path: {file_path_str}\n"
                f"Pass file exists: {file_exists}\n"
                f"Pass file mtime (raw datetime): {file_mtime_dt} (ts={file_mtime_ts})\n"
                f"DB updated_at vs File mtime: DB={raw_updated_at} | File={file_mtime_dt}\n"
                "------------------------------------"
            )
            logger.warning(diag_msg)
            print(diag_msg, flush=True)

            if is_greater:
                updated_serials.append(r.serial_number)
        else:
            logger.warning(f"[CHECK_UPDATED_PASSES DIAGNOSTIC] WalletPass not found for serial={r.serial_number}, appending fallback")
            print(f"[CHECK_UPDATED_PASSES DIAGNOSTIC] WalletPass not found for serial={r.serial_number}, appending fallback", flush=True)
            updated_serials.append(r.serial_number)

    last_updated_tag = str(max_updated_ts if max_updated_ts > 0 else int(datetime.datetime.utcnow().timestamp() * 1_000_000))
    will_return_status = "HTTP 204 No Content" if (passesUpdatedSince and not updated_serials) else "HTTP 200 OK"

    summary_diag = (
        "------------------------------------\n"
        "[CHECK_UPDATED_PASSES SUMMARY]\n"
        f"updated_serials before returning: {updated_serials}\n"
        f"max_updated_ts: {max_updated_ts}\n"
        f"lastUpdated value returned to Apple: {last_updated_tag}\n"
        f"HTTP response that will be returned: {will_return_status}\n"
        "------------------------------------"
    )
    logger.warning(summary_diag)
    print(summary_diag, flush=True)

    if passesUpdatedSince and not updated_serials:
        duration_ms = (time.time() - start_time) * 1000
        exit_msg = f"[OTA LOGS] EXIT GET /devices | Status: 204 (No Updated Passes since {passesUpdatedSince}) | Duration: {duration_ms:.2f}ms"
        logger.warning(exit_msg)
        print(exit_msg, flush=True)
        return Response(status_code=204)

    duration_ms = (time.time() - start_time) * 1000
    exit_msg = (
        f"[OTA LOGS] EXIT GET /devices | Status: 200 | serialNumbers={updated_serials} | "
        f"lastUpdated={last_updated_tag} | Duration: {duration_ms:.2f}ms"
    )
    logger.warning(exit_msg)
    print(exit_msg, flush=True)

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
    print("ENTER download_updated_passkit_pass", flush=True)
    logger.warning("ENTER download_updated_passkit_pass")
    start_time = time.time()
    auth_present = bool(authorization)
    auth_token = (authorization or "").replace("ApplePass ", "").strip()

    entry_msg = (
        f"[OTA LOGS] ENTRY GET /passes | serial={serial_number} | "
        f"pass_type={pass_type_identifier} | Auth Header Present: {auth_present}"
    )
    logger.warning(entry_msg)
    print(entry_msg, flush=True)

    pass_rec = db.query(WalletPass).filter(WalletPass.serial_number == serial_number).first()
    auth_matched = bool(pass_rec and (not pass_rec.authentication_token or pass_rec.authentication_token == auth_token))

    logger.warning(f"[OTA LOGS] Authentication token matched: {auth_matched}")
    print(f"[OTA LOGS] Authentication token matched: {auth_matched}", flush=True)

    if not pass_rec or (pass_rec.authentication_token and pass_rec.authentication_token != auth_token):
        duration_ms = (time.time() - start_time) * 1000
        exit_msg = f"[OTA LOGS] EXIT GET /passes | Status: 401 Unauthorized | Duration: {duration_ms:.2f}ms"
        logger.warning(exit_msg)
        print(exit_msg, flush=True)
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Only regenerate if file is missing on server disk (prevents redundant regenerations on every GET request)
    if not pass_rec.pass_file_path or not Path(pass_rec.pass_file_path).exists():
        if pass_rec.customer_package_id:
            from app.models.customer_package import CustomerPackage
            from app.models.user import User
            cp = db.query(CustomerPackage).filter(CustomerPackage.id == pass_rec.customer_package_id).first()
            if cp:
                cust = db.query(User).filter(User.id == cp.customer_id).first()
                try:
                    logger.warning(f"[OTA LOGS] Pass file missing on disk, generating pass for {serial_number}")
                    WalletService.update_wallet_pass_on_usage(db, cp, cust)
                    db.refresh(pass_rec)
                except Exception as e:
                    logger.warning(f"[OTA LOGS] Could not regenerate pass before PassKit download: {e}")

    file_path = Path(pass_rec.pass_file_path) if pass_rec.pass_file_path else None
    file_exists = file_path.exists() if file_path else False
    file_size = file_path.stat().st_size if (file_exists and file_path) else 0

    logger.warning(f"[OTA LOGS] File Path: {file_path} | Exists: {file_exists} | Size: {file_size} bytes")
    print(f"[OTA LOGS] File Path: {file_path} | Exists: {file_exists} | Size: {file_size} bytes", flush=True)

    if not file_exists:
        duration_ms = (time.time() - start_time) * 1000
        exit_msg = f"[OTA LOGS] EXIT GET /passes | Status: 404 Not Found | Duration: {duration_ms:.2f}ms"
        logger.warning(exit_msg)
        print(exit_msg, flush=True)
        raise HTTPException(status_code=404, detail="Pass file missing")

    duration_ms = (time.time() - start_time) * 1000
    exit_msg = f"[OTA LOGS] EXIT GET /passes | Status: 200 OK | Duration: {duration_ms:.2f}ms"
    logger.warning(exit_msg)
    print(exit_msg, flush=True)

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
