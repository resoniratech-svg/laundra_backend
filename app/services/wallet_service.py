import traceback
import uuid
import datetime
import logging
from sqlalchemy.orm import Session
from typing import Optional

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
    def generate_google_wallet_link(package: CustomerPackage, customer_name: str = "Customer", company_name: str = "Laundra Laundry") -> str:
        """Disabled as per user request"""
        return ""

    @staticmethod
    def create_and_save_wallet_pass(
        db: Session,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company_name: str = "Laundra Laundry"
    ) -> dict:
        """
        Phase 9 & Phase 10: Purchase Orchestrator
        Generates QR Code, Apple Wallet, Google Wallet and persists metadata.
        """
        status = {"google_wallet": False, "apple_wallet": False, "qr_code": False}
        cust_name = customer.name if customer else "Customer"
        pkg_title = package.package.name if hasattr(package, 'package') and package.package else "Prepaid Package"
        exp_str = package.expiry_date.strftime('%Y-%m-%d') if package.expiry_date else "N/A"
        bal_str = f"QR {float(package.current_balance or package.package_value or 0.0):.2f}"

        try:
            wallet_pass = None
            if package.customer_id:
                wallet_pass = (
                    db.query(WalletPass)
                    .filter(WalletPass.customer_id == package.customer_id)
                    .order_by(WalletPass.created_at.desc())
                    .first()
                )

            if not wallet_pass:
                wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()

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
        except Exception as e:
            logger.error(f"Database error persisting wallet pass metadata for package {package.id}: {e}")
            db.rollback()
            return {"google_wallet": False, "apple_wallet": False, "qr_code": False}

        return status

    @staticmethod
    def update_wallet_pass_on_usage(
        db: Session,
        package: CustomerPackage,
        customer: Optional[User] = None
    ):
        """
        Automatic Wallet Updates when balance/washes decrease, package is renewed, or status changes.
        Regenerates PKPass with dynamic card theme.
        """
        logger.warning("[DEBUG] ENTERED update_wallet_pass_on_usage package_id=%s", package.id)
        print("[PRINT DEBUG] ENTERED update_wallet_pass_on_usage", flush=True)
        try:
            cust_name = customer.name if customer else "Customer"
            wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
            
            exp_str = package.expiry_date.strftime('%Y-%m-%d') if (package.expiry_date and hasattr(package.expiry_date, 'strftime')) else str(package.expiry_date or "N/A")
            bal_str = f"QR {float(package.current_balance or package.package_value or 0.0):.2f}"
            pkg_title = package.package.name if hasattr(package, 'package') and package.package else "Prepaid Package"

            if wallet_pass:
                wallet_pass.pass_status = package.status or "ACTIVE"

            raw_updated_at_before = getattr(wallet_pass, 'updated_at', None) if wallet_pass else None
            raw_created_at_before = getattr(wallet_pass, 'created_at', None) if wallet_pass else None
            w_id_before = getattr(wallet_pass, 'id', None) if wallet_pass else None
            s_num_before = getattr(wallet_pass, 'serial_number', None) if wallet_pass else None

            logger.warning("[DEBUG] ABOUT TO REGENERATE PASS package_id=%s", package.id)
            print("[PRINT DEBUG] ABOUT TO REGENERATE PASS", flush=True)
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
                package_obj=package
            )
            print("[PRINT DEBUG] PASS REGENERATED", flush=True)
            import logging
            logging.getLogger("app.api.v1.prepaid_packages").warning("[TEST] Reached line immediately after PASS REGENERATED print")
            print("[PRINT DEBUG] BEFORE logger.warning PASS REGENERATED", flush=True)
            logger.warning("[DEBUG] PASS REGENERATED package_id=%s", package.id)
            print("[PRINT DEBUG] AFTER logger.warning PASS REGENERATED", flush=True)
            logger.info(f"[OTA Lifecycle] 1. Package updated: package_id={package.id}, status={package.status}")
            logger.info(f"[OTA Lifecycle] 2. Pass regenerated for package_id={package.id}")

            raw_updated_at_mid = getattr(wallet_pass, 'updated_at', None) if wallet_pass else None
            raw_created_at_mid = getattr(wallet_pass, 'created_at', None) if wallet_pass else None
            w_id_mid = getattr(wallet_pass, 'id', None) if wallet_pass else None
            s_num_mid = getattr(wallet_pass, 'serial_number', None) if wallet_pass else None
            utc_now_mid = datetime.datetime.utcnow()

            diag_before_commit = (
                "------------------------------------\n"
                "[WALLET PASS UPDATE DIAGNOSTIC - BEFORE COMMIT]\n"
                f"WalletPass ID: {w_id_mid or w_id_before}\n"
                f"Serial Number: {s_num_mid or s_num_before}\n"
                f"updated_at BEFORE modification: {raw_updated_at_before}\n"
                f"updated_at AFTER modification (before commit): {raw_updated_at_mid}\n"
                f"created_at: {raw_created_at_mid or raw_created_at_before}\n"
                f"Current UTC time: {utc_now_mid}\n"
                "------------------------------------"
            )
            logger.warning(diag_before_commit)
            print(diag_before_commit, flush=True)

            print("[PRINT DEBUG] BEFORE DB COMMIT", flush=True)
            db.commit()
            print("[PRINT DEBUG] AFTER DB COMMIT", flush=True)

            if wallet_pass:
                try:
                    db.refresh(wallet_pass)
                except Exception:
                    pass

            raw_updated_at_after = getattr(wallet_pass, 'updated_at', None) if wallet_pass else None
            raw_created_at_after = getattr(wallet_pass, 'created_at', None) if wallet_pass else None
            w_id_after = getattr(wallet_pass, 'id', None) if wallet_pass else None
            s_num_after = getattr(wallet_pass, 'serial_number', None) if wallet_pass else None

            diag_after_commit = (
                "------------------------------------\n"
                "[WALLET PASS UPDATE DIAGNOSTIC - AFTER COMMIT & REFRESH]\n"
                f"WalletPass ID: {w_id_after}\n"
                f"Serial Number: {s_num_after}\n"
                f"updated_at AFTER commit (after db.refresh): {raw_updated_at_after}\n"
                f"created_at: {raw_created_at_after}\n"
                f"Current UTC time: {datetime.datetime.utcnow()}\n"
                "------------------------------------"
            )
            logger.warning(diag_after_commit)
            print(diag_after_commit, flush=True)

            # Trigger APNs Over-the-Air (OTA) push notification to all registered iOS devices
            try:
                print("[PRINT DEBUG] BEFORE APNS IMPORT", flush=True)
                from app.services.apple_wallet.apns_service import APNsService
                apns = APNsService()
                print("[PRINT DEBUG] APNS SERVICE CREATED", flush=True)
                wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
                serial_num = (wallet_pass.serial_number if wallet_pass and wallet_pass.serial_number else (wallet_pass.apple_serial_number if wallet_pass else None)) or f"PASS-{str(package.id).replace('-', '').upper()[:12]}"
                logger.info(f"[OTA Lifecycle] 3. Querying registered iOS devices for serial_number={serial_num}")
                logger.warning("[DEBUG] ABOUT TO SEND APNS package_id=%s serial=%s", package.id, serial_num)
                print("[PRINT DEBUG] BEFORE notify_devices_for_pass", flush=True)
                summary = apns.notify_devices_for_pass(db, serial_num)
                print("[PRINT DEBUG] AFTER notify_devices_for_pass", flush=True)
                logger.warning("[DEBUG] APNS CALL FINISHED package_id=%s summary=%s", package.id, summary)
                logger.info(f"[OTA Lifecycle] 4 & 5. APNs push lifecycle completed for {serial_num}: {summary}")
            except Exception as e_apns:
                logger.exception(f"[APNs] Failed to send push notification for package {package.id}: {e_apns}")

            print("[PRINT DEBUG] EXITING update_wallet_pass_on_usage", flush=True)
        except Exception as e:
            logger.exception(f"Error updating wallet pass for package {package.id}: {e}")
            db.rollback()

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
        package_obj: Optional[CustomerPackage] = None
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

        if not wallet_pass and package_obj:
            wallet_pass = db.query(WalletPass).filter(
                (WalletPass.customer_package_id == package_obj.id) |
                (WalletPass.wallet_object_id == f"OBJ-{pkg_hex}") |
                (WalletPass.google_object_id == f"GOBJ-{pkg_hex}")
            ).first()

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
        pkpass_path = pass_service.generate_pkpass(pass_data, serial_number=serial_number)

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
            wallet_pass.wallet_object_id = f"OBJ-{pkg_hex}"
            wallet_pass.google_object_id = f"GOBJ-{pkg_hex}"
            wallet_pass.class_id = f"CLASS-LAUNDRA-{tenant_hex}"
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

