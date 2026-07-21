import uuid
import logging
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.models.customer_package import CustomerPackage
from app.models.wallet_pass import WalletPass
from app.models.user import User
from app.wallet.object_service import create_wallet_object
from app.wallet.jwt_service import generate_add_to_wallet_url
from app.wallet.exceptions import WalletException

logger = logging.getLogger(__name__)

class WalletService:
    @staticmethod
    def generate_google_wallet_link(package: CustomerPackage, customer_name: str = "Customer", company_name: str = "Laundra Laundry") -> str:
        """
        Orchestrates Google Wallet object building and signed JWT save URL generation.
        Phase 13: Includes graceful exception handling fallback.
        """
        try:
            pkg_title = package.package.name if hasattr(package, 'package') and package.package else "Prepaid Package"
            exp_str = package.expiry_date.strftime('%Y-%m-%d') if package.expiry_date else "N/A"
            
            wallet_obj = create_wallet_object(
                customer_package_id=str(package.id),
                customer_name=customer_name,
                package_name=pkg_title,
                company_name=company_name,
                remaining_balance=float(package.current_balance or 0.0),
                remaining_quantity=package.total_quantity - package.used_quantity if package.total_quantity is not None else None,
                expiry_date_str=exp_str,
                status=package.status or "ACTIVE",
                secure_token=package.secure_token
            )
            
            save_url = generate_add_to_wallet_url(wallet_obj["payload"])
            return save_url
        except Exception as e:
            logger.error(f"Error generating Google Wallet link for package {package.id}: {e}")
            # Fallback URL if token/JWT generation encounters issue
            return f"https://pay.google.com/gp/v/save/fallback_{str(package.id)[:8]}"

    @staticmethod
    def create_and_save_wallet_pass(
        db: Session,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company_name: str = "Laundra Laundry"
    ) -> WalletPass:
        """
        Phase 9 & Phase 10: Purchase Orchestrator
        - Creates Google Wallet Object
        - Generates Add to Google Wallet Link
        - Saves / Updates record in wallet_passes DB table
        - Updates customer_package.google_wallet_url
        """
        cust_name = customer.name if customer else "Customer"
        google_url = WalletService.generate_google_wallet_link(package, customer_name=cust_name, company_name=company_name)
        package.google_wallet_url = google_url
        
        # Generate Apple Wallet Pass URL
        try:
            pkg_title = package.package.name if hasattr(package, 'package') and package.package else "Prepaid Package"
            exp_str = package.expiry_date.strftime('%Y-%m-%d') if package.expiry_date else "N/A"
            bal_str = f"QR {float(package.current_balance or package.package_value or 0.0):.2f}"
            apple_res = WalletService.generate_real_apple_wallet_pass(
                db=db,
                tenant_id=package.tenant_id,
                customer_id=package.customer_id,
                customer_name=cust_name,
                package_name=pkg_title,
                remaining_balance=bal_str,
                expiry_date=exp_str
            )
            if apple_res and apple_res.get("download_url"):
                package.apple_wallet_url = apple_res["download_url"]
        except Exception as apple_err:
            logger.error(f"Error generating Apple Wallet pass for package {package.id}: {apple_err}")

        issuer_id = settings.GOOGLE_WALLET_ISSUER_ID
        clean_id = str(package.id).replace("-", "")
        object_id = f"{issuer_id}.customer_{clean_id}"
        class_id = settings.GOOGLE_WALLET_CLASS_ID

        # Phase 13: Graceful pass update / insertion (handles existing customer package pass)
        try:
            wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
            if not wallet_pass:
                wallet_pass = WalletPass(
                    company_id=package.tenant_id,
                    customer_id=package.customer_id,
                    customer_package_id=package.id,
                    class_id=class_id,
                    wallet_object_id=object_id,
                    wallet_url=google_url,
                    status=package.status or "ACTIVE"
                )
                db.add(wallet_pass)
            else:
                wallet_pass.class_id = class_id
                wallet_pass.wallet_object_id = object_id
                wallet_pass.wallet_url = google_url
                wallet_pass.status = package.status or "ACTIVE"
                
            db.commit()
            db.refresh(package)
            return wallet_pass
        except Exception as err:
            logger.error(f"Database error persisting wallet pass for package {package.id}: {err}")
            db.rollback()
            return None

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
            google_url = WalletService.generate_google_wallet_link(package, customer_name=cust_name)
            package.google_wallet_url = google_url
            
            wallet_pass = db.query(WalletPass).filter(WalletPass.customer_package_id == package.id).first()
            if wallet_pass:
                wallet_pass.wallet_url = google_url
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
        order_id: Optional[uuid.UUID] = None
    ) -> dict:
        from app.services.apple_wallet.pass_service import PassService
        from app.schemas.apple_wallet import LaundryPassData
        from app.models.wallet_pass import WalletPass

        serial_number = f"PASS-{uuid.uuid4().hex[:8].upper()}"
        auth_token = uuid.uuid4().hex
        qr_token = f"https://laundry.example.com/verify/pass/{serial_number}?token={auth_token}"

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

        return {
            "success": True,
            "pass_id": wallet_pass.id,
            "serial_number": serial_number,
            "download_url": f"/api/v1/wallet/apple/pass/{wallet_pass.id}",
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

