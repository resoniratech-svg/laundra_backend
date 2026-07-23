import traceback
import uuid
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
            wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
            if not wallet_pass:
                wallet_pass = WalletPass(
                    tenant_id=package.tenant_id,
                    customer_id=package.customer_id,
                    customer_package_id=package.id,
                    original_amount=float(package.package_value or 0.0),
                    remaining_balance=float(package.current_balance or 0.0),
                    expiry_date=package.expiry_date,
                    status=package.status or "ACTIVE",
                    wallet_status="ACTIVE"
                )
                db.add(wallet_pass)
                db.flush()
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
                wallet_pass.qr_token = f"https://laundry.example.com/verify/pass/{serial_number}?token={auth_token}"
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
                package_secure_token=package.secure_token
            )
            if apple_res and apple_res.get("download_url"):
                logger.info("Apple Wallet Generated Successfully")
                logger.info(f"Apple Wallet URL Generated: {apple_res['download_url']}")
                logger.info("Saving Apple Wallet URL")
                
                package.apple_wallet_url = apple_res["download_url"]
                wallet_pass.apple_pass_url = apple_res["download_url"]
                status["apple_wallet"] = True
                
                logger.info("Apple Wallet URL Saved")
        except Exception:
            db.rollback()   # <-- VERY IMPORTANT
            logger.exception(
                f"Error generating Apple Wallet pass for package {package.id}"
            )
            
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
        Phase 11: Automatic Wallet Updates when balance/washes decrease or status changes.
        """
        try:
            cust_name = customer.name if customer else "Customer"
            
            wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
            if wallet_pass:
                wallet_pass.pass_status = package.status or "ACTIVE"
            
            db.commit()
        except Exception as e:
            logger.error(f"Error updating wallet pass for package {package.id}: {e}")
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
        package_secure_token: Optional[str] = None
    ) -> dict:
        from app.services.apple_wallet.pass_service import PassService
        from app.schemas.apple_wallet import LaundryPassData
        from app.models.wallet_pass import WalletPass

        serial_number = wallet_pass.apple_serial_number if wallet_pass and wallet_pass.apple_serial_number else f"PASS-{uuid.uuid4().hex[:8].upper()}"
        auth_token = wallet_pass.authentication_token if wallet_pass and wallet_pass.authentication_token else uuid.uuid4().hex
        qr_token = wallet_pass.qr_token if wallet_pass and wallet_pass.qr_token else f"https://laundry.example.com/verify/pass/{serial_number}?token={auth_token}"

        pass_data = LaundryPassData(
            customer_name=customer_name,
            package_name=package_name,
            package_id=str(order_id or serial_number),
            remaining_balance=remaining_balance,
            expiry_date=expiry_date or "N/A",
            qr_data=qr_token
        )

        pass_service = PassService()
        pkpass_path = pass_service.generate_pkpass(pass_data, serial_number=serial_number)

        if not wallet_pass:
            wallet_pass = WalletPass(
                tenant_id=tenant_id,
                customer_id=customer_id,
                order_id=order_id,
                pass_type_identifier=settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER,
                serial_number=serial_number,
                authentication_token=auth_token,
                qr_token=qr_token,
                status="ACTIVE",
                pass_file_path=str(pkpass_path)
            )
            db.add(wallet_pass)
            db.commit()
            db.refresh(wallet_pass)
        else:
            wallet_pass.pass_type_identifier = settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER
            wallet_pass.serial_number = serial_number
            wallet_pass.authentication_token = auth_token
            wallet_pass.qr_token = qr_token
            wallet_pass.pass_file_path = str(pkpass_path)
            wallet_pass.apple_serial_number = serial_number
            wallet_pass.apple_pass_type_identifier = settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER
            # db.commit() will be called by orchestrator

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
        if package.current_balance <= 0 or package.status in ['COMPLETED', 'FULLY_UTILIZED', 'EXPIRED']:
            return "WHITE"
        
        if package.package_value and package.package_value > 0:
            ratio = float(package.current_balance) / float(package.package_value)
            if ratio < 0.15:
                return "ORANGE"
            elif ratio < 1.0:
                return "GREY"
                
        return "GOLD"

