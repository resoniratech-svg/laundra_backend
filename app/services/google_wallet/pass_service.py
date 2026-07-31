import logging
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.customer_package import CustomerPackage
from app.models.wallet_pass import WalletPass
from app.models.user import User
from app.models.company import Company
from app.services.google_wallet.class_service import GoogleWalletClassService
from app.services.google_wallet.object_service import GoogleWalletObjectService
from app.services.google_wallet.jwt_service import GoogleWalletJwtService
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

class GoogleWalletPassService:
    @classmethod
    def generate_google_wallet_pass(
        cls,
        db: Session,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company: Optional[Company] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates Google Wallet Pass creation & Save URL generation:
        1. Ensures GenericClass exists.
        2. Constructs GenericObject & creates/fetches from Google API.
        3. Generates signed Save to Google Wallet URL.
        4. Persists metadata to WalletPass and CustomerPackage in DB.
        """
        logger.info(f"[GoogleWallet] START Pass Generation | package_id={package.id}")

        try:
            # 1. Ensure GenericClass exists
            class_res = GoogleWalletClassService.get_or_create_generic_class()
            class_id = class_res["class_id"]

            # Resolve customer and company if missing
            if not customer and package.customer_id:
                customer = db.query(User).filter(User.id == package.customer_id).first()
            if not company and package.tenant_id:
                company = db.query(Company).filter(Company.id == package.tenant_id).first()

            # 2. Create or fetch GenericObject
            object_res = GoogleWalletObjectService.get_or_create_generic_object(
                package=package,
                customer=customer,
                company=company
            )
            object_id = object_res["object_id"]
            object_payload = object_res["data"]

            # 3. Generate signed Save-to-Wallet URL & Clean Backend Redirect Path
            raw_save_url = GoogleWalletJwtService.generate_save_url(object_payload=object_payload)
            clean_redirect_url = f"/api/v1/wallet/google/pass/{package.secure_token or package.id}"

            # 4. Persist clean backend URL to CustomerPackage & WalletPass in DB
            package.google_wallet_url = clean_redirect_url

            wallet_pass = WalletService.resolve_wallet_pass(
                db=db,
                customer_package_id=package.id,
                customer_id=package.customer_id
            )

            now_dt = datetime.datetime.utcnow()
            if not wallet_pass:
                pkg_hex = str(package.id).replace('-', '').upper()[:12]
                wallet_pass = WalletPass(
                    tenant_id=package.tenant_id,
                    customer_id=package.customer_id,
                    customer_package_id=package.id,
                    created_at=now_dt,
                    updated_at=now_dt,
                    google_class_id=class_id,
                    google_object_id=object_id,
                    google_wallet_url=clean_redirect_url,
                    pass_status=package.status or "ACTIVE",
                    wallet_status="ACTIVE"
                )
                db.add(wallet_pass)
            else:
                wallet_pass.google_class_id = class_id
                wallet_pass.google_object_id = object_id
                wallet_pass.google_wallet_url = clean_redirect_url
                wallet_pass.updated_at = now_dt

            db.commit()
            db.refresh(package)
            db.refresh(wallet_pass)

            logger.info(f"[GoogleWallet] SUCCESS Pass Generation | object_id={object_id}")

            return {
                "success": True,
                "class_id": class_id,
                "object_id": object_id,
                "google_wallet_url": clean_redirect_url,
                "raw_save_url": raw_save_url,
                "wallet_pass_id": str(wallet_pass.id)
            }

        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Pass Generation | package_id={package.id} | reason={str(e)}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
