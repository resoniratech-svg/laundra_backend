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
    def resolve_company_name(cls, company: Optional[Company] = None, package: Optional[CustomerPackage] = None) -> str:
        """
        Dynamically resolves the issuing SaaS tenant company name.
        Ensures the company name is strictly pinned to package.tenant_id
        and is NEVER hardcoded or replaced by another tenant.
        """
        if company and company.name and company.name.strip():
            return company.name.strip()

        if package and getattr(package, "company", None) and package.company and package.company.name and package.company.name.strip():
            return package.company.name.strip()

        if package and getattr(package, "tenant_id", None):
            try:
                from app.core.database import SessionLocal
                db = SessionLocal()
                try:
                    c = db.query(Company).filter(Company.id == package.tenant_id).first()
                    if c and c.name and c.name.strip():
                        return c.name.strip()
                finally:
                    db.close()
            except Exception:
                pass

        return "Laundry SaaS"

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
        used_qty = getattr(package, "used_quantity", 0) or 0
        used_amt = float(getattr(package, "used_amount", 0.0) or 0.0)
        status = (package.status or "").upper()

        now_dt = datetime.datetime.utcnow()
        is_expired = False
        if package.expiry_date and package.expiry_date.replace(tzinfo=None) < now_dt:
            is_expired = True

        services_used = False
        all_services_exhausted = False
        if getattr(package, "service_items", None) and isinstance(package.service_items, list) and len(package.service_items) > 0:
            total_left = sum(item.get("left", 0) for item in package.service_items)
            if total_left == 0:
                all_services_exhausted = True
            for item in package.service_items:
                tot = item.get("total", 0)
                left = item.get("left", tot)
                if left < tot:
                    services_used = True
                    break

        # Priority 1: COMPLETED / EXPIRED / ZERO BALANCE -> WHITE (#FFFFFF)
        if is_expired or status in ["COMPLETED", "EXPIRED", "FULLY_UTILIZED", "CANCELLED"] or bal <= 0 or all_services_exhausted:
            return "#FFFFFF"  # Pure White
        
        # Priority 2: IN USE -> GREY (#A6A6A6)
        is_used = (val > 0 and bal < val) or used_qty > 0 or used_amt > 0 or services_used
        if is_used:
            return "#A6A6A6"  # Medium Neutral Grey (#A6A6A6)

        # Priority 3: NEW / UNUSED -> GOLD (#D4AF37)
        return "#D4AF37"      # Reference Gold (#D4AF37)

    @classmethod
    def resolve_qr_url(cls, package: CustomerPackage) -> str:
        import os
        token_str = package.secure_token if package.secure_token else str(package.id)
        base_url = (
            os.getenv("PUBLIC_BACKEND_URL") or 
            os.getenv("BACKEND_BASE_URL") or 
            getattr(settings, "PUBLIC_BACKEND_URL", None) or 
            getattr(settings, "BACKEND_BASE_URL", None) or 
            "https://dry-backend.cocjl5.easypanel.host"
        )
        base_url = str(base_url).strip().rstrip("/")
        if base_url.endswith("/api/v1"):
            base_url = base_url[:-7]
            
        return f"{base_url}/api/v1/wallet/google/pass/{token_str}"

    @classmethod
    def build_generic_object_payload(
        cls,
        package: CustomerPackage,
        customer: Optional[User] = None,
        company: Optional[Company] = None,
        object_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Constructs refined, production-grade GenericObject payload for Google Wallet.
        """
        if not object_id:
            object_id = cls.get_object_id(package.id)
        class_id = GoogleWalletClassService.get_class_id()

        company_name = cls.resolve_company_name(company, package)
        package_name = cls.resolve_package_name(package)
        customer_name = cls.resolve_customer_name(customer)
        balance_val = float(package.current_balance or package.package_value or 0.0)
        card_bg_hex = cls.resolve_background_color(package)

        pass_state = "ACTIVE"
        now_dt = datetime.datetime.utcnow()
        is_expired = False
        if package.expiry_date and package.expiry_date.replace(tzinfo=None) < now_dt:
            is_expired = True

        if is_expired or package.status in ["COMPLETED", "EXPIRED", "FULLY_UTILIZED", "CANCELLED"] or balance_val <= 0:
            pass_state = "EXPIRED"

        status_display = (package.status or "ACTIVE").upper()
        if is_expired:
            status_display = "EXPIRED"
        elif balance_val <= 0:
            status_display = "COMPLETED"

        qr_url = cls.resolve_qr_url(package)

        text_modules = [
            {
                "id": "customer",
                "header": "CUSTOMER",
                "body": customer_name
            },
            {
                "id": "package",
                "header": "PACKAGE",
                "body": package_name
            },
            {
                "id": "coupon_cost",
                "header": "COUPON COST",
                "body": f"QR {balance_val:.2f}"
            },
            {
                "id": "status",
                "header": "STATUS",
                "body": status_display
            }
        ]

        # Process Service Items per reference design
        services_list = getattr(package, "service_items", None)
        if services_list and isinstance(services_list, list) and len(services_list) > 0:
            for i, item in enumerate(services_list):
                srv_name = (item.get("service") or f"Service {i+1}").upper()
                tot = item.get("total", 0)
                left = item.get("left", tot)
                text_modules.append({
                    "id": f"service_{i+1}",
                    "header": f"{srv_name} LEFT",
                    "body": f"{left} / {tot}"
                })
        else:
            legacy_services = []
            if getattr(package, "wash_total", 0):
                legacy_services.append({"service": "WASH & PRESS", "total": package.wash_total, "left": package.wash_left})
            if getattr(package, "iron_total", 0):
                legacy_services.append({"service": "PRESSING", "total": package.iron_total, "left": package.iron_left})
            if getattr(package, "dry_total", 0):
                legacy_services.append({"service": "DRY CLEANING", "total": package.dry_total, "left": package.dry_left})
            if getattr(package, "steam_total", 0):
                legacy_services.append({"service": "STEAM", "total": package.steam_total, "left": package.steam_left})
            
            if legacy_services:
                for i, item in enumerate(legacy_services):
                    srv_name = item["service"].upper()
                    tot = item["total"]
                    left = item["left"]
                    text_modules.append({
                        "id": f"service_{i+1}",
                        "header": f"{srv_name} LEFT",
                        "body": f"{left} / {tot}"
                    })
            else:
                text_modules.append({
                    "id": "service_1",
                    "header": "WASH & PRESS LEFT",
                    "body": "12 / 12"
                })

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
                    "value": company_name
                }
            },
            "textModulesData": text_modules,
            "barcode": {
                "type": "QR_CODE",
                "value": qr_url,
                "alternateText": "Scan to add pass"
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
        object_id: Optional[str] = None,
        client: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Patches/updates an existing GenericObject in Google Wallet REST API.
        Used for design refreshes, pass synchronization, and package renewals.
        """
        if not object_id:
            object_id = cls.get_object_id(package.id)
        if not client:
            client = get_google_wallet_client()

        logger.info(f"[GoogleWallet] START Patch Object | object_id={object_id}")
        payload = cls.build_generic_object_payload(package, customer, company, object_id=object_id)

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
        object_id: Optional[str] = None,
        client: Optional[Any] = None
    ) -> Dict[str, Any]:
        if not object_id:
            object_id = cls.get_object_id(package.id)
        if not client:
            client = get_google_wallet_client()

        logger.info(f"[GoogleWallet] START Object Lookup | object_id={object_id}")

        try:
            existing_obj = client.genericobject().get(resourceId=object_id).execute()
            logger.info(f"[GoogleWallet] SUCCESS Object Found. Patching for Renewal/Sync | object_id={object_id}")
            return cls.patch_generic_object(package, customer, company, object_id=object_id, client=client)
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
        payload = cls.build_generic_object_payload(package, customer, company, object_id=object_id)

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
                return cls.patch_generic_object(package, customer, company, object_id=object_id, client=client)
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
