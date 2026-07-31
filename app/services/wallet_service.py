import traceback
import uuid
import datetime
import logging
from sqlalchemy.orm import Session
from typing import Optional, Union, Any

from app.core.config import settings
from app.models.customer_package import CustomerPackage
from app.models.wallet_pass import WalletPass
from app.models.user import User


logger = logging.getLogger(__name__)
async def generic_exception_handler(request, exc):
    logger.exception("Unhandled exception")
    traceback.print_exc()

    raise exc
class WalletService:
    @staticmethod
    def resolve_wallet_pass(
        db: Session,
        serial_number: Optional[str] = None,
        customer_id: Optional[Union[str, uuid.UUID]] = None,
        customer_package_id: Optional[Union[str, uuid.UUID]] = None,
        identifier: Optional[Union[str, uuid.UUID]] = None
    ) -> Optional[WalletPass]:
        """
        Single, centralized source of truth for all WalletPass lookups.

        Supported Priority:
        1. identifier (Generic resolution for download / public endpoints):
           a) CustomerPackage.secure_token == identifier
           b) CustomerPackage.id == identifier
           c) WalletPass.id == identifier (Logs legacy link usage)
           d) WalletPass.serial_number / apple_serial_number / authentication_token == identifier
        2. serial_number (Apple PassKit routes)
        3. customer_id (Permanent Wallet identity)
        4. customer_package_id (Fallback only)
        """
        if identifier:
            ident_str = str(identifier).strip()

            # 1a. Check CustomerPackage.secure_token
            cp = db.query(CustomerPackage).filter(CustomerPackage.secure_token == ident_str).first()
            if not cp:
                # 1b. Check CustomerPackage.id (UUID)
                try:
                    cp_uuid = uuid.UUID(ident_str) if not isinstance(identifier, uuid.UUID) else identifier
                    cp = db.query(CustomerPackage).filter(CustomerPackage.id == cp_uuid).first()
                except (ValueError, TypeError, AttributeError):
                    pass

            if cp:
                wp = db.query(WalletPass).filter(WalletPass.customer_package_id == cp.id).first()
                if wp:
                    return wp
                if cp.customer_id:
                    wp = db.query(WalletPass).filter(WalletPass.customer_id == cp.customer_id).order_by(WalletPass.created_at.desc()).first()
                    if wp:
                        return wp

            # 1c. Check WalletPass.id (UUID) — Legacy URL handling
            try:
                wp_uuid = uuid.UUID(ident_str) if not isinstance(identifier, uuid.UUID) else identifier
                wp = db.query(WalletPass).filter(WalletPass.id == wp_uuid).first()
                if wp:
                    logger.info(f"[Legacy Pass URL] Resolved WalletPass via legacy WalletPass.id identifier={ident_str}")
                    return wp
            except (ValueError, TypeError, AttributeError):
                pass

            # 1d. Check WalletPass.serial_number / apple_serial_number / authentication_token
            wp = db.query(WalletPass).filter(
                (WalletPass.serial_number == ident_str) |
                (WalletPass.apple_serial_number == ident_str) |
                (WalletPass.authentication_token == ident_str)
            ).first()
            if wp:
                logger.info(f"[Legacy Pass URL] Resolved WalletPass via serial/auth_token identifier={ident_str}")
                return wp

        if serial_number:
            wallet_pass = (
                db.query(WalletPass)
                .filter(
                    (WalletPass.serial_number == serial_number) |
                    (WalletPass.apple_serial_number == serial_number) |
                    (WalletPass.authentication_token == serial_number)
                )
                .first()
            )
            if wallet_pass:
                return wallet_pass

        if customer_package_id:
            cp_uuid = uuid.UUID(str(customer_package_id)) if isinstance(customer_package_id, str) else customer_package_id
            wallet_pass = (
                db.query(WalletPass)
                .filter(WalletPass.customer_package_id == cp_uuid)
                .first()
            )
            if wallet_pass:
                return wallet_pass

        if customer_id:
            c_uuid = uuid.UUID(str(customer_id)) if isinstance(customer_id, str) else customer_id
            wallet_pass = (
                db.query(WalletPass)
                .filter(WalletPass.customer_id == c_uuid)
                .order_by(WalletPass.created_at.desc())
                .first()
            )
            if wallet_pass:
                return wallet_pass

        return None

    @staticmethod
    def generate_google_wallet_link(package: CustomerPackage, customer_name: str = "Customer", company_name: str = "Laundra Laundry") -> str:
        """Disabled as per user request"""
        return ""

    @staticmethod
    def create_and_save_wallet_pass(
        db: Session,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company_name: str = "Laundra Laundry",
        ctx: Optional[Any] = None
    ) -> dict:
        """
        Phase 9 & Phase 10: Purchase Orchestrator
        Generates QR Code, Apple Wallet, Google Wallet and persists metadata.
        """
        from app.services.apple_wallet.telemetry import TraceContext, WalletLogger
        if not ctx:
            ctx = TraceContext()

        WalletLogger.log("info", "WalletPass", "START DB Creation", ctx, customer_id=package.customer_id, package_id=package.id)

        status = {"google_wallet": False, "apple_wallet": False, "qr_code": False}
        cust_name = customer.name if customer else "Customer"
        pkg_title = package.package.name if hasattr(package, 'package') and package.package else "Prepaid Package"
        exp_str = package.expiry_date.strftime('%Y-%m-%d') if package.expiry_date else "N/A"
        bal_str = f"QR {float(package.current_balance or package.package_value or 0.0):.2f}"

        try:
            wallet_pass = WalletService.resolve_wallet_pass(
                db=db,
                customer_id=package.customer_id,
                customer_package_id=package.id
            )

            pkg_hex = str(package.id).replace('-', '')[:12].upper()
            tenant_hex = str(package.tenant_id).replace('-', '')[:8].upper()
            serial_str = f"PASS-{pkg_hex[:8]}"
            auth_tok = str(uuid.uuid4()).replace('-', '')
            pass_url = f"/api/v1/wallet/apple/pass/{package.secure_token or package.id}"

            if not wallet_pass:
                wallet_pass = WalletPass(
                    tenant_id=package.tenant_id,
                    customer_id=package.customer_id,
                    customer_package_id=package.id,
                    original_amount=float(package.package_value or 0.0),
                    remaining_balance=float(package.current_balance or 0.0),
                    expiry_date=package.expiry_date,
                    status=package.status or "ACTIVE",
                    wallet_status="ACTIVE",
                    wallet_object_id=f"OBJ-{pkg_hex}",
                    class_id=f"CLASS-LAUNDRA-{tenant_hex}",
                    pass_type_identifier="pass.com.laundry.wallet",
                    apple_pass_type_identifier="pass.com.laundry.wallet",
                    serial_number=serial_str,
                    apple_serial_number=serial_str,
                    authentication_token=auth_tok,
                    wallet_url=pass_url
                )
                db.add(wallet_pass)
                db.flush()
                WalletLogger.log(
                    "info", "WalletPass", "SUCCESS DB Creation", ctx,
                    wallet_pass_id=wallet_pass.id,
                    serial_number=serial_str,
                    auth_token=WalletLogger.mask(auth_tok),
                    initial_updated_at=wallet_pass.wallet_updated_at or wallet_pass.created_at
                )
            else:
                wallet_pass.customer_package_id = package.id
                wallet_pass.original_amount = float(package.package_value or 0.0)
                wallet_pass.remaining_balance = float(package.current_balance or package.package_value or 0.0)
                wallet_pass.expiry_date = package.expiry_date
                wallet_pass.status = package.status or "ACTIVE"
                wallet_pass.pass_status = package.status or "ACTIVE"
                if not wallet_pass.wallet_object_id:
                    wallet_pass.wallet_object_id = f"OBJ-{pkg_hex}"
                if not wallet_pass.class_id:
                    wallet_pass.class_id = f"CLASS-LAUNDRA-{tenant_hex}"
                if not wallet_pass.wallet_url:
                    wallet_pass.wallet_url = wallet_pass.apple_pass_url or pass_url
                if not wallet_pass.serial_number:
                    wallet_pass.serial_number = wallet_pass.apple_serial_number or serial_str
                if not wallet_pass.authentication_token:
                    wallet_pass.authentication_token = auth_tok
        except Exception as e:
            logger.error(f"Failed to fetch/create WalletPass for package {package.id}: {e}")
            return status

        # 1. QR Code Generation
        try:
            from app.services.apple_wallet.qr_service import QRService
            qr_service = QRService()
            if not wallet_pass.qr_token:
                serial_number = wallet_pass.apple_serial_number or f"PASS-{uuid.uuid4().hex[:8].upper()}"
                auth_token = wallet_pass.authentication_token or uuid.uuid4().hex
                base_backend = getattr(settings, "BACKEND_BASE_URL", "https://laundry-project-laundry-backend.cocjl5.easypanel.host").rstrip("/")
                wallet_pass.qr_token = f"{base_backend}/verify/pass/{serial_number}?token={auth_token}"
                wallet_pass.apple_serial_number = serial_number
                wallet_pass.authentication_token = auth_token
                wallet_pass.serial_number = serial_number

            qr_path = qr_service.generate(wallet_pass.qr_token)
            if qr_path:
                wallet_pass.qr_url = f"/api/v1/wallet/qr/{qr_path.name}"
                status["qr_code"] = True
        except Exception as e:
            logger.error(f"Error generating QR Code for package {package.id}: {e}")



        # 2. Google Wallet Generation (Isolated runtime execution)
        if getattr(settings, "GOOGLE_WALLET_ENABLED", True):
            try:
                from app.services.google_wallet.pass_service import GoogleWalletPassService
                logger.info(f"Starting Google Wallet Generation for package {package.id}")
                gw_res = GoogleWalletPassService.generate_google_wallet_pass(
                    db=db,
                    package=package,
                    customer=customer
                )
                if gw_res and gw_res.get("success"):
                    status["google_wallet"] = True
                    logger.info(f"Google Wallet Generated Successfully for package {package.id}")
            except Exception as e_gw:
                logger.error(f"Error generating Google Wallet pass for package {package.id}: {e_gw}")

        # 3. Apple Wallet
        try:
            logger.info("Starting Apple Wallet Generation")
            apple_res = WalletService.generate_real_apple_wallet_pass(
                db=db,
                tenant_id=package.tenant_id,
                customer_id=package.customer_id,
                customer_name=cust_name,
                package_name=pkg_title,
                remaining_balance=bal_str,
                expiry_date=exp_str,
                wallet_pass=wallet_pass,
                package_secure_token=package.secure_token,
                package_obj=package
            )
            if apple_res and apple_res.get("download_url"):
                logger.info("Apple Wallet Generated Successfully")
                logger.info(f"Apple Wallet URL Generated: {apple_res['download_url']}")
                logger.info("Saving Apple Wallet URL")
                
                package.apple_wallet_url = apple_res["download_url"]
                wallet_pass.apple_pass_url = apple_res["download_url"]
                status["apple_wallet"] = True
                
                logger.info("Apple Wallet URL Saved")
        except Exception as e:
            db.rollback()
            logger.error(f"Error generating Apple Wallet pass for package {package.id}: {e}")
            
        try:
            db.commit()
            db.refresh(package)
            # Trigger APNs OTA Push Notification via unified helper
            WalletService._notify_wallet_update(db, wallet_pass)
        except Exception as e:
            logger.error(f"Database error persisting wallet pass metadata for package {package.id}: {e}")
            db.rollback()
            return {"google_wallet": False, "apple_wallet": False, "qr_code": False}

        return status

    @staticmethod
    def _notify_wallet_update(db: Session, wallet_pass: Optional[WalletPass]) -> dict:
        """
        Unified helper to trigger APNs Over-the-Air (OTA) push notifications
        whenever a WalletPass is updated, renewed, or consumed.
        """
        if not wallet_pass:
            logger.warning("[APNs OTA] Cannot send push notification: wallet_pass is None")
            return {"sent": 0, "failed": 0, "status": "skipped_no_pass"}

        serial_num = wallet_pass.serial_number or wallet_pass.apple_serial_number
        if not serial_num:
            logger.warning("[APNs OTA] Cannot send push notification: serial_number missing on wallet_pass")
            return {"sent": 0, "failed": 0, "status": "skipped_no_serial"}

        try:
            from app.services.apple_wallet.apns_service import APNsService
            apns = APNsService()
            summary = apns.notify_devices_for_pass(db, serial_num)
            logger.info(f"[OTA Lifecycle] APNs push lifecycle completed for {serial_num}: {summary}")
            return summary
        except Exception as e_apns:
            logger.exception(f"[APNs] Failed to send push notification for serial={serial_num}: {e_apns}")
            return {"sent": 0, "failed": 0, "error": str(e_apns)}

    @staticmethod
    def update_wallet_pass_on_usage(
        db: Session,
        package: CustomerPackage,
        customer: Optional[User] = None,
        background_tasks=None,
        ctx: Optional[Any] = None
    ):
        """
        Automatic Wallet Updates when balance/washes decrease, package is renewed, or status changes.
        Regenerates PKPass with dynamic card theme.
        """
        from app.services.apple_wallet.telemetry import TraceContext, WalletLogger
        if not ctx:
            ctx = TraceContext()

        ctx.mark_stage("pass_regen_start")
        WalletLogger.log("info", "OTA", "START Workflow", ctx, package_id=package.id, customer_id=package.customer_id)

        try:
            cust_name = customer.name if customer else "Customer"
            wallet_pass = WalletService.resolve_wallet_pass(
                db=db,
                customer_id=package.customer_id,
                customer_package_id=package.id
            )
            
            exp_str = package.expiry_date.strftime('%Y-%m-%d') if (package.expiry_date and hasattr(package.expiry_date, 'strftime')) else str(package.expiry_date or "N/A")
            bal_str = f"QR {float(package.current_balance or package.package_value or 0.0):.2f}"
            pkg_title = package.package.name if hasattr(package, 'package') and package.package else "Prepaid Package"

            if wallet_pass:
                wallet_pass.pass_status = package.status or "ACTIVE"

            # Log DB State BEFORE Commit
            if wallet_pass:
                WalletLogger.log_db_diff(
                    ctx=ctx,
                    entity_name="WalletPass",
                    entity_id=wallet_pass.id,
                    stage="BEFORE",
                    updated_at=wallet_pass.updated_at,
                    balance=bal_str,
                    status=wallet_pass.status,
                    remaining_items=package.wash_left
                )

            # Synchronous: Regenerate pass (generate JSON, sign, zip, save to disk)
            WalletService.generate_real_apple_wallet_pass(
                db=db,
                tenant_id=package.tenant_id,
                customer_id=package.customer_id,
                customer_name=cust_name,
                package_name=pkg_title,
                remaining_balance=bal_str,
                expiry_date=exp_str,
                wallet_pass=wallet_pass,
                package_secure_token=package.secure_token,
                package_obj=package,
                ctx=ctx
            )

            # Synchronous: Patch Google Wallet object on usage (updates balance, services, status & theme)
            if getattr(settings, "GOOGLE_WALLET_ENABLED", True):
                try:
                    from app.services.google_wallet.object_service import GoogleWalletObjectService
                    gw_obj_id = wallet_pass.google_object_id if (wallet_pass and wallet_pass.google_object_id) else None
                    GoogleWalletObjectService.patch_generic_object(
                        package=package,
                        customer=customer,
                        object_id=gw_obj_id
                    )
                    logger.info(f"[GoogleWallet] Successfully patched live object on usage for package {package.id}")
                except Exception as e_gw_patch:
                    logger.error(f"[GoogleWallet] Failed to patch object on usage for package {package.id}: {e_gw_patch}")

            # Mark sync status as PENDING before committing (APNs push is deferred)
            if wallet_pass:
                wallet_pass.wallet_sync_status = "PENDING"
                wallet_pass.wallet_sync_attempts = 0
                wallet_pass.wallet_sync_error = None

            # Synchronous: Commit WalletPass changes to DB (pass file already on disk)
            db.commit()

            if wallet_pass:
                try:
                    db.refresh(wallet_pass)
                except Exception:
                    pass

            # Log DB State AFTER Commit
            if wallet_pass:
                WalletLogger.log_db_diff(
                    ctx=ctx,
                    entity_name="WalletPass",
                    entity_id=wallet_pass.id,
                    stage="AFTER",
                    updated_at=wallet_pass.updated_at,
                    balance=bal_str,
                    status=wallet_pass.status,
                    remaining_items=package.wash_left
                )

            # Dispatch APNs push notification as background task
            serial_num = None
            if wallet_pass:
                serial_num = wallet_pass.serial_number or wallet_pass.apple_serial_number
            wallet_pass_id = str(wallet_pass.id) if wallet_pass else None
            tenant_id = str(package.tenant_id)
            tr_id = ctx.trace_id

            if background_tasks and serial_num:
                background_tasks.add_task(
                    WalletService._async_apns_with_retry,
                    serial_number=serial_num,
                    wallet_pass_id=wallet_pass_id,
                    tenant_id=tenant_id,
                    trace_id=tr_id
                )
                WalletLogger.log("info", "OTA", "APNs Dispatched to Background", ctx, serial_number=serial_num)
            elif serial_num:
                # Fallback: send synchronously if no background_tasks available
                WalletService._notify_wallet_update(db, wallet_pass)
                WalletLogger.log("info", "OTA", "APNs Dispatched Synchronously", ctx, serial_number=serial_num)
            else:
                WalletLogger.log("warning", "OTA", "Skipped APNs Push (No Serial)", ctx)

        except Exception as e:
            logger.exception(f"Error updating wallet pass for package {package.id}: {e}")
    @staticmethod
    def _async_apns_with_retry(
        serial_number: str,
        wallet_pass_id: str,
        tenant_id: str,
        max_attempts: int = 4,
        backoff_schedule: list = None,
        trace_id: Optional[str] = None
    ):
        """
        Background task: Send APNs push notification with exponential backoff retry.
        """
        import time as _time
        from app.core.database import SessionLocal
        from app.services.apple_wallet.telemetry import TraceContext, WalletLogger

        ctx = TraceContext(trace_id=trace_id) if trace_id else TraceContext()

        if backoff_schedule is None:
            backoff_schedule = [0, 30, 120, 600]

        WalletLogger.log("info", "APNs", "START Background Push", ctx, serial_number=serial_number)

        for attempt in range(1, max_attempts + 1):
            wait_seconds = backoff_schedule[attempt - 1] if attempt - 1 < len(backoff_schedule) else 600
            if wait_seconds > 0:
                logger.info(f"[APNs Background] Attempt {attempt}/{max_attempts}: waiting {wait_seconds}s before retry for serial={serial_number}")
                _time.sleep(wait_seconds)

            bg_db = SessionLocal()
            try:
                from app.services.apple_wallet.apns_service import APNsService
                apns = APNsService()
                summary = apns.notify_devices_for_pass(bg_db, serial_number)

                sent = summary.get("sent", 0)
                total = summary.get("total", 0)

                if total == 0:
                    # No devices registered — nothing to push to. Mark as synced.
                    logger.info(f"[APNs Background] No registered devices for serial={serial_number}. Marking SYNCED.")
                    bg_db.query(WalletPass).filter(WalletPass.id == wallet_pass_id).update(
                        {
                            WalletPass.wallet_sync_status: "SYNCED",
                            WalletPass.wallet_sync_attempts: attempt,
                            WalletPass.wallet_sync_error: None,
                            WalletPass.updated_at: WalletPass.updated_at
                        },
                        synchronize_session=False
                    )
                    bg_db.commit()
                    return

                if sent > 0:
                    # At least one device successfully received the push
                    logger.info(f"[APNs Background] SUCCESS: Attempt {attempt}/{max_attempts} sent to {sent}/{total} devices for serial={serial_number}")
                    bg_db.query(WalletPass).filter(WalletPass.id == wallet_pass_id).update(
                        {
                            WalletPass.wallet_sync_status: "SYNCED",
                            WalletPass.wallet_sync_attempts: attempt,
                            WalletPass.wallet_sync_error: None,
                            WalletPass.updated_at: WalletPass.updated_at
                        },
                        synchronize_session=False
                    )
                    bg_db.commit()
                    return
                else:
                    error_msg = f"Attempt {attempt}: APNs returned 0 successful pushes out of {total} devices"
                    logger.warning(f"[APNs Background] {error_msg} for serial={serial_number}")
                    new_status = "PENDING" if attempt < max_attempts else "FAILED"
                    bg_db.query(WalletPass).filter(WalletPass.id == wallet_pass_id).update(
                        {
                            WalletPass.wallet_sync_status: new_status,
                            WalletPass.wallet_sync_attempts: attempt,
                            WalletPass.wallet_sync_error: error_msg,
                            WalletPass.updated_at: WalletPass.updated_at
                        },
                        synchronize_session=False
                    )
                    bg_db.commit()

            except Exception as e:
                error_msg = f"Attempt {attempt}: {type(e).__name__}: {str(e)}"
                logger.exception(f"[APNs Background] FAILED: {error_msg} for serial={serial_number}")
                try:
                    new_status = "PENDING" if attempt < max_attempts else "FAILED"
                    bg_db.query(WalletPass).filter(WalletPass.id == wallet_pass_id).update(
                        {
                            WalletPass.wallet_sync_status: new_status,
                            WalletPass.wallet_sync_attempts: attempt,
                            WalletPass.wallet_sync_error: error_msg,
                            WalletPass.updated_at: WalletPass.updated_at
                        },
                        synchronize_session=False
                    )
                    bg_db.commit()
                except Exception:
                    bg_db.rollback()
            finally:
                bg_db.close()

        logger.error(f"[APNs Background] EXHAUSTED all {max_attempts} attempts for serial={serial_number}. Status: FAILED.")

    @staticmethod
    def generate_apple_wallet_link(package: CustomerPackage) -> str:
        mock_id = str(uuid.uuid4())[:8]
        return f"https://wallet.apple.com/add/pass/mock_{mock_id}"

    @staticmethod
    def generate_real_apple_wallet_pass(
        db: Session,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_name: str,
        package_name: str,
        remaining_balance: str,
        expiry_date: Optional[str] = None,
        order_id: Optional[uuid.UUID] = None,
        wallet_pass: Optional['WalletPass'] = None,
        package_secure_token: Optional[str] = None,
        package_obj: Optional[CustomerPackage] = None,
        ctx: Optional[Any] = None
    ) -> dict:
        from app.services.apple_wallet.pass_service import PassService
        from app.schemas.apple_wallet import LaundryPassData
        from app.models.wallet_pass import WalletPass

        # Ensure deterministic serial_number & pass identity based on CustomerPackage ID
        if package_obj:
            pkg_hex = str(package_obj.id).replace('-', '').upper()[:12]
        elif wallet_pass and wallet_pass.customer_package_id:
            pkg_hex = str(wallet_pass.customer_package_id).replace('-', '').upper()[:12]
        else:
            pkg_hex = uuid.uuid4().hex[:12].upper()

        if not wallet_pass:
            wallet_pass = WalletService.resolve_wallet_pass(
                db=db,
                customer_id=customer_id,
                customer_package_id=package_obj.id if package_obj else None
            )

        if wallet_pass and (wallet_pass.serial_number or wallet_pass.apple_serial_number):
            serial_number = wallet_pass.serial_number or wallet_pass.apple_serial_number
        elif package_obj:
            pkg_hex = str(package_obj.id).replace('-', '').upper()[:12]
            serial_number = f"PASS-{pkg_hex}"
        else:
            serial_number = f"PASS-{uuid.uuid4().hex[:8].upper()}"

        auth_token = wallet_pass.authentication_token if wallet_pass and wallet_pass.authentication_token else uuid.uuid4().hex
        base_backend = getattr(settings, "BACKEND_BASE_URL", "https://laundry-project-laundry-backend.cocjl5.easypanel.host").rstrip("/")
        qr_token = wallet_pass.qr_token if wallet_pass and wallet_pass.qr_token else f"{base_backend}/verify/pass/{serial_number}?token={auth_token}"

        w_left = getattr(package_obj, "wash_left", 0) if package_obj else 0
        w_total = getattr(package_obj, "wash_total", 0) if package_obj else 0
        i_left = getattr(package_obj, "iron_left", 0) if package_obj else 0
        i_total = getattr(package_obj, "iron_total", 0) if package_obj else 0
        d_left = getattr(package_obj, "dry_left", 0) if package_obj else 0
        d_total = getattr(package_obj, "dry_total", 0) if package_obj else 0
        s_left = getattr(package_obj, "steam_left", 0) if package_obj else 0
        s_total = getattr(package_obj, "steam_total", 0) if package_obj else 0

        c_cost = "QR 0.00"
        if package_obj and hasattr(package_obj, 'package') and package_obj.package:
            price_val = float(package_obj.package.offer_price or package_obj.package.original_price or 0.0)
            c_cost = f"QR {price_val:.2f}"
        elif package_obj and package_obj.package_value:
            c_cost = f"QR {float(package_obj.package_value):.2f}"

        # Resolve dynamic tenant/company name
        from app.models.company import Company
        resolved_tenant_id = tenant_id or (package_obj.tenant_id if package_obj else None)
        comp_obj = db.query(Company).filter(Company.id == resolved_tenant_id).first() if resolved_tenant_id else None
        dynamic_company_name = comp_obj.name if (comp_obj and comp_obj.name) else "Laundra"

        pass_data = LaundryPassData(
            company_name=dynamic_company_name,
            customer_name=customer_name,
            package_name=package_name,
            package_id=str(order_id or serial_number),
            remaining_balance=remaining_balance,
            expiry_date=expiry_date or "N/A",
            qr_data=qr_token,
            coupon_cost=c_cost,
            auth_token=auth_token,
            status=package_obj.status if package_obj and package_obj.status else "ACTIVE",
            service_items=getattr(package_obj, "service_items", []) or [],
            wash_left=w_left,
            wash_total=w_total,
            iron_left=i_left,
            iron_total=i_total,
            dry_left=d_left,
            dry_total=d_total,
            steam_left=s_left,
            steam_total=s_total
        )

        pass_service = PassService()
        pkpass_path = pass_service.generate_pkpass(pass_data, serial_number=serial_number, ctx=ctx)

        pass_sec_token = package_secure_token or (package_obj.secure_token if package_obj else None) or serial_number
        pass_url = f"/api/v1/wallet/apple/pass/{pass_sec_token}"
        pkg_hex = str(package_obj.id if package_obj else (wallet_pass.customer_package_id if wallet_pass else uuid.uuid4())).replace('-', '').upper()[:12]
        tenant_hex = str(tenant_id).replace('-', '').upper()[:8]

        if not wallet_pass:
            now_dt = datetime.datetime.utcnow()
            wallet_pass = WalletPass(
                tenant_id=tenant_id,
                customer_id=customer_id,
                customer_package_id=package_obj.id if package_obj else None,
                order_id=order_id,
                created_at=now_dt,
                updated_at=now_dt,
                wallet_created_at=now_dt,
                wallet_updated_at=now_dt,
                pass_type_identifier=settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER,
                apple_pass_type_identifier=settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER,
                serial_number=serial_number,
                apple_serial_number=serial_number,
                authentication_token=auth_token,
                qr_token=qr_token,
                status="ACTIVE",
                wallet_status="ACTIVE",
                wallet_object_id=f"OBJ-{pkg_hex}",
                google_object_id=f"GOBJ-{pkg_hex}",
                class_id=f"CLASS-LAUNDRA-{tenant_hex}",
                google_class_id=f"GCLASS-LAUNDRA-{tenant_hex}",
                wallet_url=pass_url,
                apple_pass_url=pass_url,
                pass_file_path=str(pkpass_path)
            )
            db.add(wallet_pass)
            db.commit()
            db.refresh(wallet_pass)
        else:
            wallet_pass.updated_at = datetime.datetime.utcnow()
            if not wallet_pass.wallet_object_id:
                wallet_pass.wallet_object_id = f"OBJ-{pkg_hex}"
            if not wallet_pass.google_object_id:
                wallet_pass.google_object_id = f"GOBJ-{pkg_hex}"
            if not wallet_pass.class_id:
                wallet_pass.class_id = f"CLASS-LAUNDRA-{tenant_hex}"
            if not wallet_pass.google_class_id:
                wallet_pass.google_class_id = f"GCLASS-LAUNDRA-{tenant_hex}"

            wallet_pass.wallet_url = pass_url
            wallet_pass.apple_pass_url = pass_url
            wallet_pass.pass_type_identifier = settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER
            wallet_pass.apple_pass_type_identifier = settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER
            wallet_pass.serial_number = serial_number
            wallet_pass.apple_serial_number = serial_number
            wallet_pass.authentication_token = auth_token
            wallet_pass.qr_token = qr_token
            wallet_pass.pass_file_path = str(pkpass_path)
            wallet_pass.pass_status = package_obj.status if package_obj and package_obj.status else "ACTIVE"

        download_url = f"/api/v1/wallet/apple/pass/{package_secure_token}" if package_secure_token else f"/api/v1/wallet/apple/pass/{wallet_pass.id}"
        
        return {
            "success": True,
            "pass_id": wallet_pass.id,
            "serial_number": serial_number,
            "download_url": download_url,
            "file_path": str(pkpass_path)
        }

    @staticmethod
    def update_pass_color(package: CustomerPackage) -> str:
        """
        Dynamic Theme Resolver:
        - WHITE: Expired, Completed, or 0 balance
        - GREY: Started using package (current_balance < package_value)
        - GOLD: Purchased & no services consumed yet (current_balance == package_value)
        """
        import datetime
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        is_expired = False
        if package.expiry_date:
            exp_str = package.expiry_date.strftime('%Y-%m-%d') if hasattr(package.expiry_date, 'strftime') else str(package.expiry_date)
            if exp_str < today_str:
                is_expired = True

        pkg_status = (package.status or '').upper()
        if is_expired or pkg_status in ['COMPLETED', 'FULLY_UTILIZED', 'EXPIRED'] or float(package.current_balance or 0) <= 0:
            return "WHITE"

        val = float(package.package_value or 0)
        bal = float(package.current_balance or 0)

        if val > 0 and bal < val:
            return "GREY"

        return "GOLD"

