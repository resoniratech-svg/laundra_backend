import logging
import re
import datetime
from typing import Dict, Any, Optional, List
from googleapiclient.errors import HttpError
from app.core.config import settings
from app.models.customer_package import CustomerPackage
from app.models.user import User
from app.models.company import Company
from app.services.google_wallet.client import get_google_wallet_client
from app.services.google_wallet.class_service import GoogleWalletClassService

logger = logging.getLogger(__name__)

class GoogleWalletObjectService:
    @staticmethod
    def get_object_id(package_id: Any) -> str:
        """
        Generates a deterministic, Google-compliant GenericObject ID:
        {ISSUER_ID}.pkg_{clean_package_uuid}
        """
        issuer_id = settings.GOOGLE_WALLET_ISSUER_ID
        if not issuer_id:
            raise ValueError("GOOGLE_WALLET_ISSUER_ID is not configured.")
        
        clean_uuid = re.sub(r'[^a-zA-Z0-9_-]', '', str(package_id))
        return f"{issuer_id}.pkg_{clean_uuid}"

    @classmethod
    def resolve_company_name(cls, company: Optional[Company] = None) -> str:
        raw_name = (company.name if company and company.name else "").strip()
        if not raw_name or raw_name.lower() in ["iron", "wash", "dry", "steam", "service", "test"]:
            return "Laundra Laundry"
        return raw_name

    @classmethod
    def resolve_package_name(cls, package: CustomerPackage) -> str:
        if hasattr(package, 'package') and package.package and package.package.name:
            return package.package.name
        return "Prepaid Laundry Package"

    @classmethod
    def resolve_customer_name(cls, customer: Optional[User] = None) -> str:
        if customer and customer.name:
            return customer.name
        return "Valued Customer"

    @classmethod
    def format_expiry_date(cls, expiry_date: Optional[datetime.datetime]) -> str:
        if not expiry_date:
            return "N/A"
        try:
            return expiry_date.strftime('%d %b %Y')
        except Exception:
            return str(expiry_date)

    @classmethod
    def format_services_summary(cls, package: CustomerPackage) -> str:
        summary_items: List[str] = []
        if getattr(package, "service_items", None) and isinstance(package.service_items, list):
            for item in package.service_items:
                s_name = item.get("service", "Service")
                s_left = item.get("left", item.get("total", 0))
                s_tot = item.get("total", 0)
                if s_tot > 0:
                    summary_items.append(f"{s_name}: {s_left} / {s_tot}")
        else:
            if getattr(package, "wash_total", 0):
                summary_items.append(f"Wash: {package.wash_left} / {package.wash_total}")
            if getattr(package, "iron_total", 0):
                summary_items.append(f"Ironing: {package.iron_left} / {package.iron_total}")
            if getattr(package, "dry_total", 0):
                summary_items.append(f"Dry Clean: {package.dry_left} / {package.dry_total}")
            if getattr(package, "steam_total", 0):
                summary_items.append(f"Steam: {package.steam_left} / {package.steam_total}")

        if summary_items:
            return " | ".join(summary_items)
        
        balance_val = float(package.current_balance or package.package_value or 0.0)
        return f"Full Package Access (QR {balance_val:.2f})"

    @classmethod
    def resolve_background_color(cls, package: CustomerPackage) -> str:
        bal = float(package.current_balance or package.package_value or 0.0)
        val = float(package.package_value or 0.0)
        status = (package.status or "").upper()

        if status in ["COMPLETED", "EXPIRED", "FULLY_UTILIZED", "CANCELLED"] or bal <= 0:
            return "#64748B"  # Muted Grey (Expired/Exhausted)
        elif val > 0 and bal < val:
            return "#334155"  # Slate Grey (In Use)
        return "#D97706"      # Premium Vibrant Gold/Amber (New/Active Gold Package)

    @classmethod
    def build_generic_object_payload(
        cls,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company: Optional[Company] = None
    ) -> Dict[str, Any]:
        """
        Constructs refined, production-grade GenericObject payload for Google Wallet.
        """
        object_id = cls.get_object_id(package.id)
        class_id = GoogleWalletClassService.get_class_id()

        company_name = cls.resolve_company_name(company)
        package_name = cls.resolve_package_name(package)
        customer_name = cls.resolve_customer_name(customer)
        balance_val = float(package.current_balance or package.package_value or 0.0)
        expiry_formatted = cls.format_expiry_date(package.expiry_date)
        services_formatted = cls.format_services_summary(package)
        card_bg_hex = cls.resolve_background_color(package)

        pass_state = "ACTIVE"
        if package.status in ["COMPLETED", "EXPIRED", "FULLY_UTILIZED", "CANCELLED"]:
            pass_state = "EXPIRED"

        qr_value = package.secure_token if package.secure_token else str(package.id)

        text_modules = [
            {
                "id": "customer",
                "header": "CUSTOMER",
                "body": customer_name
            },
            {
                "id": "balance",
                "header": "REMAINING BALANCE",
                "body": f"QR {balance_val:.2f}"
            },
            {
                "id": "expiry",
                "header": "VALID UNTIL",
                "body": expiry_formatted
            },
            {
                "id": "services",
                "header": "REMAINING SERVICES",
                "body": services_formatted
            }
        ]

        payload = {
            "id": object_id,
            "classId": class_id,
            "state": pass_state,
            "cardTitle": {
                "defaultValue": {
                    "language": "en-US",
                    "value": company_name
                }
            },
            "header": {
                "defaultValue": {
                    "language": "en-US",
                    "value": package_name
                }
            },
            "textModulesData": text_modules,
            "barcode": {
                "type": "QR_CODE",
                "value": qr_value
            },
            "hexBackgroundColor": card_bg_hex
        }

        return payload

    @classmethod
    def patch_generic_object(
        cls,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company: Optional[Company] = None,
        client: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Patches/updates an existing GenericObject in Google Wallet REST API.
        Used for design refreshes and pass synchronization.
        """
        object_id = cls.get_object_id(package.id)
        if not client:
            client = get_google_wallet_client()

        logger.info(f"[GoogleWallet] START Patch Object | object_id={object_id}")
        payload = cls.build_generic_object_payload(package, customer, company)

        try:
            patched_obj = client.genericobject().patch(resourceId=object_id, body=payload).execute()
            logger.info(f"[GoogleWallet] SUCCESS Patch Object | object_id={object_id}")
            return {
                "status": "PATCHED",
                "object_id": object_id,
                "data": patched_obj
            }
        except HttpError as err:
            logger.error(f"[GoogleWallet] FAILURE Patch Object | object_id={object_id} | status={err.resp.status} | reason={err}")
            raise
        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Patch Object | object_id={object_id} | reason={str(e)}")
            raise

    @classmethod
    def get_or_create_generic_object(
        cls,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company: Optional[Company] = None,
        client: Optional[Any] = None
    ) -> Dict[str, Any]:
        object_id = cls.get_object_id(package.id)
        if not client:
            client = get_google_wallet_client()

        logger.info(f"[GoogleWallet] START Object Lookup | object_id={object_id}")

        try:
            existing_obj = client.genericobject().get(resourceId=object_id).execute()
            logger.info(f"[GoogleWallet] SUCCESS Object Found | object_id={object_id}")
            return {
                "status": "EXISTS",
                "object_id": object_id,
                "data": existing_obj
            }
        except HttpError as err:
            if err.resp.status in [404, 400]:
                logger.info(f"[GoogleWallet] Object NOT FOUND ({err.resp.status}). Proceeding to create | object_id={object_id}")
            else:
                logger.error(f"[GoogleWallet] FAILURE Object Lookup | object_id={object_id} | status={err.resp.status} | reason={err}")
                raise
        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Object Lookup | object_id={object_id} | reason={str(e)}")
            raise

        logger.info(f"[GoogleWallet] START Object Creation | object_id={object_id}")
        payload = cls.build_generic_object_payload(package, customer, company)

        try:
            created_obj = client.genericobject().insert(body=payload).execute()
            logger.info(f"[GoogleWallet] SUCCESS Object Created | object_id={object_id}")
            return {
                "status": "CREATED",
                "object_id": object_id,
                "data": created_obj
            }
        except HttpError as err:
            if err.resp.status == 409:
                logger.info(f"[GoogleWallet] Object 409 Conflict (Already Exists). Patching | object_id={object_id}")
                return cls.patch_generic_object(package, customer, company, client)
            logger.error(f"[GoogleWallet] FAILURE Object Creation | object_id={object_id} | status={err.resp.status} | reason={err}")
            raise
        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Object Creation | object_id={object_id} | reason={str(e)}")
            raise

    @classmethod
    def get_generic_object(cls, object_id: str, client: Optional[Any] = None) -> Dict[str, Any]:
        if not client:
            client = get_google_wallet_client()
        logger.info(f"[GoogleWallet] START Fetch Object | object_id={object_id}")
        try:
            res = client.genericobject().get(resourceId=object_id).execute()
            logger.info(f"[GoogleWallet] SUCCESS Fetch Object | object_id={object_id}")
            return res
        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Fetch Object | object_id={object_id} | reason={str(e)}")
            raise
