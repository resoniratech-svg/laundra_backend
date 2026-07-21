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
