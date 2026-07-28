import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import settings
from app.schemas.apple_wallet import WalletPassModel, PassStructure, PassField, Barcode, BarcodeFormat, LaundryPassData
from app.services.apple_wallet.certificate_service import CertificateService
from app.services.apple_wallet.image_service import ImageService
from app.services.apple_wallet.manifest_service import ManifestService
from app.services.apple_wallet.package_service import PackageService
from app.services.apple_wallet.signing_service import SigningService
from app.services.apple_wallet.template_service import TemplateService
from app.services.apple_wallet.utils import temporary_directory

logger = logging.getLogger("apple_wallet.pass_service")

class PassService:
    """Service responsible for generating pass.json and packaging Apple Wallet passes."""

    def __init__(
        self,
        cert_service: Optional[CertificateService] = None,
        image_service: Optional[ImageService] = None,
        template_service: Optional[TemplateService] = None,
        manifest_service: Optional[ManifestService] = None,
        signing_service: Optional[SigningService] = None,
        package_service: Optional[PackageService] = None
    ):
        p_template = Path(settings.APPLE_WALLET_TEMPLATE_PATH)
        self.template = p_template / "pass.json" if p_template.is_dir() else p_template
        output_base = Path(settings.APPLE_WALLET_GENERATED_PATH)
        self.output = output_base / "pass"
        self.output.mkdir(parents=True, exist_ok=True)

        self.cert_service = cert_service or CertificateService()
        self.image_service = image_service or ImageService()
        self.template_service = template_service or TemplateService()
        self.manifest_service = manifest_service or ManifestService(self.output)
        self.signing_service = signing_service or SigningService(self.output)
        self.package_service = package_service or PackageService(self.output)

    @staticmethod
    def resolve_card_theme(
        service_items: list = None,
        is_expired: bool = False,
        explicit_status: str = None,
        # Legacy params kept for backward compat
        wash_left: int = 0, wash_total: int = 0,
        iron_left: int = 0, iron_total: int = 0,
        dry_left: int = 0, dry_total: int = 0,
    ) -> Dict[str, str]:
        """
        Dynamic Apple Wallet Card Themes:
        - Gold: Purchased & no services consumed yet -> Status: ACTIVE (rgb(230,190,60))
        - Grey: In use & services consumed -> Status: IN USE (rgb(185,185,185))
        - White: Expired or Completed -> Status: EXPIRED / COMPLETED (rgb(255,255,255))
        """
        exp_upper = (explicit_status or "").upper()
        if is_expired or exp_upper == "EXPIRED":
            return {
                "status": "EXPIRED",
                "backgroundColor": "rgb(255, 255, 255)",
                "foregroundColor": "rgb(0, 0, 0)",
                "labelColor": "rgb(100, 100, 100)"
            }

        # Compute totals from service_items if available
        items = service_items or []
        total_left = sum(si.get("left", 0) for si in items) if items else ((wash_left or 0) + (iron_left or 0) + (dry_left or 0))
        total_all = sum(si.get("total", 0) for si in items) if items else ((wash_total or 0) + (iron_total or 0) + (dry_total or 0))

        if total_left <= 0 or exp_upper in ["COMPLETED", "FULLY_UTILIZED"]:
            return {
                "status": "COMPLETED",
                "backgroundColor": "rgb(255, 255, 255)",
                "foregroundColor": "rgb(0, 0, 0)",
                "labelColor": "rgb(100, 100, 100)"
            }

        # Check if brand new (0 items deducted)
        is_brand_new = True
        if items:
            for si in items:
                if si.get("total", 0) > 0 and si.get("left", 0) < si.get("total", 0):
                    is_brand_new = False
                    break
        else:
            if wash_total > 0 and wash_left < wash_total:
                is_brand_new = False
            if iron_total > 0 and iron_left < iron_total:
                is_brand_new = False
            if dry_total > 0 and dry_left < dry_total:
                is_brand_new = False

        if is_brand_new and exp_upper != "IN USE":
            return {
                "status": "ACTIVE",
                "backgroundColor": "rgb(230, 190, 60)",
                "foregroundColor": "rgb(0, 0, 0)",
                "labelColor": "rgb(60, 60, 60)"
            }

        return {
            "status": "IN USE",
            "backgroundColor": "rgb(185, 185, 185)",
            "foregroundColor": "rgb(0, 0, 0)",
            "labelColor": "rgb(60, 60, 60)"
        }

    def generate(self, data: LaundryPassData, serial_number: Optional[str] = None) -> Path:
        """Generates pass.json file from LaundryPassData schema with dynamic card theme switching."""
        raw_template = self.template_service.load_template()

        # Use service_items if available (dynamic), else fall back to legacy fixed fields
        svc_items = getattr(data, "service_items", None) or []

        is_expired = False
        if data.expiry_date and data.expiry_date != "N/A":
            try:
                from datetime import datetime
                today_str = datetime.now().strftime("%Y-%m-%d")
                is_expired = today_str > str(data.expiry_date).split("T")[0]
            except Exception:
                is_expired = False

        theme = self.resolve_card_theme(
            service_items=svc_items,
            is_expired=is_expired,
            explicit_status=getattr(data, "status", None),
            wash_left=getattr(data, "wash_left", 0) or 0,
            wash_total=getattr(data, "wash_total", 0) or 0,
            iron_left=getattr(data, "iron_left", 0) or 0,
            iron_total=getattr(data, "iron_total", 0) or 0,
            dry_left=getattr(data, "dry_left", 0) or 0,
            dry_total=getattr(data, "dry_total", 0) or 0,
        )

        context = {
            "company_name": getattr(data, "company_name", None) or settings.APP_NAME,
            "customer_name": data.customer_name or "Member",
            "package_name": data.package_name or "Membership Pass",
            "coupon_cost": getattr(data, "coupon_cost", None) or "QR 0.00",
            "expiry_date": data.expiry_date or "N/A",
            "member_since": getattr(data, "member_since", None) or "2026",
            "status": theme["status"],
            "background_color": theme["backgroundColor"],
            "foreground_color": theme["foregroundColor"],
            "label_color": theme["labelColor"],
            "qr_data": data.qr_data or data.package_id or "PASS-DATA"
        }

        template = self.template_service.fill_placeholders(raw_template, context)

        def clean_apple_label(name: str) -> str:
            n = name.strip()
            label_map = {
                "Wash & Press": "WASH & PRESS",
                "Dry Cleaning": "DRY CLEAN",
                "Steam Press": "STEAM PRESS",
                "Wash & Fold": "WASH & FOLD",
                "Premium Services": "PREMIUM",
                "Pressing": "PRESSING",
                "Ironing": "IRONING"
            }
            if n in label_map:
                return label_map[n]
            return n.upper().replace(" LEFT", "").replace(" SERVICES", "")[:12]

        # Build auxiliaryFields DYNAMICALLY from service_items
        aux_fields = []
        if svc_items and len(svc_items) > 0:
            for si in svc_items:
                svc_name = si.get("service", "Service")
                total = si.get("total", 0)
                left = si.get("left", 0)
                if total > 0:
                    key = svc_name.lower().replace(" ", "_").replace("&", "and") + "_left"
                    label = clean_apple_label(svc_name)
                    aux_fields.append({
                        "key": key,
                        "label": label,
                        "value": f"{left} / {total}"
                    })
        else:
            # Legacy fallback: use fixed fields
            wash_l = getattr(data, "wash_left", 0) or 0
            wash_t = getattr(data, "wash_total", 0) or 0
            iron_l = getattr(data, "iron_left", 0) or 0
            iron_t = getattr(data, "iron_total", 0) or 0
            dry_l = getattr(data, "dry_left", 0) or 0
            dry_t = getattr(data, "dry_total", 0) or 0
            steam_l = getattr(data, "steam_left", 0) or 0
            steam_t = getattr(data, "steam_total", 0) or 0
            if wash_t > 0:
                aux_fields.append({"key": "wash_left", "label": "WASH & PRESS", "value": f"{wash_l} / {wash_t}"})
            if dry_t > 0:
                aux_fields.append({"key": "dry_left", "label": "DRY CLEAN", "value": f"{dry_l} / {dry_t}"})
            if iron_t > 0:
                aux_fields.append({"key": "iron_left", "label": "PRESSING", "value": f"{iron_l} / {iron_t}"})
            if steam_t > 0:
                aux_fields.append({"key": "steam_left", "label": "STEAM PRESS", "value": f"{steam_l} / {steam_t}"})

        # If no aux_fields were produced, add a default balance field (matches main behavior)
        if not aux_fields:
            aux_fields.append({
                "key": "balance",
                "label": "Balance",
                "value": data.remaining_balance
            })

        # ===================================================================
        # ALWAYS build the generic pass structure programmatically
        # (matches main branch behavior — never rely on template having it)
        # ===================================================================
        template["generic"] = {
            "headerFields": [
                {
                    "key": "status",
                    "value": theme["status"],
                    "textAlignment": "PKTextAlignmentRight"
                }
            ],
            "primaryFields": [
                {
                    "key": "customer",
                    "label": "CUSTOMER",
                    "value": context["customer_name"]
                }
            ],
            "secondaryFields": [
                {
                    "key": "package",
                    "label": "PACKAGE",
                    "value": context["package_name"]
                },
                {
                    "key": "coupon_cost",
                    "label": "COUPON COST",
                    "value": context["coupon_cost"]
                }
            ],
            "auxiliaryFields": aux_fields,
            "backFields": [
                {
                    "key": "expiry_date",
                    "label": "EXPIRY DATE",
                    "value": context["expiry_date"]
                },
                {
                    "key": "member_since",
                    "label": "MEMBER SINCE",
                    "value": context["member_since"]
                }
            ]
        }

        # ALWAYS build barcode programmatically (main does this, staging removed it)
        qr_data = data.qr_data or data.package_id or "PASS-DATA"
        template["barcode"] = {
            "format": "PKBarcodeFormatQR",
            "message": qr_data,
            "messageEncoding": "iso-8859-1",
            "altText": "Scan QR Code for verification"
        }
        template["barcodes"] = [
            {
                "format": "PKBarcodeFormatQR",
                "message": qr_data,
                "messageEncoding": "iso-8859-1",
                "altText": "Scan QR Code for verification"
            }
        ]

        base_backend = getattr(settings, "BACKEND_BASE_URL", "https://laundry-project-laundry-backend.cocjl5.easypanel.host").rstrip("/")
        web_service_url = getattr(settings, "APPLE_WALLET_WEB_SERVICE_URL", None) or f"{base_backend}/api/v1/wallet/apple"
        auth_token = getattr(data, "auth_token", None) or "AUTH-TOKEN-SECURE"

        template["passTypeIdentifier"] = settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER
        template["teamIdentifier"] = settings.APPLE_WALLET_TEAM_IDENTIFIER
        template["organizationName"] = context["company_name"]
        template["serialNumber"] = serial_number or f"PASS-{uuid.uuid4().hex[:8].upper()}"
        template["description"] = f"{context['package_name']} Pass"
        template["logoText"] = context["company_name"]
        template["backgroundColor"] = theme["backgroundColor"]
        template["foregroundColor"] = theme["foregroundColor"]
        template["labelColor"] = theme["labelColor"]
        template["webServiceURL"] = web_service_url
        template["authenticationToken"] = auth_token

        output_file = self.output / "pass.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=4, ensure_ascii=False)

        return output_file

    def generate_pkpass(self, pass_data: LaundryPassData, serial_number: Optional[str] = None) -> Path:
        s_num = serial_number or f"PASS-{uuid.uuid4().hex[:8].upper()}"
        filename = f"pass_{s_num}.pkpass"
        output_base = Path(settings.APPLE_WALLET_GENERATED_PATH)

        try:
            with temporary_directory(output_base, prefix=s_num) as temp_dir:
                logger.info(f"Temp directory: {temp_dir}")

                # 1
                self.output = temp_dir
                self.generate(pass_data, serial_number=s_num)
                logger.info("pass.json generated")

                # 2
                self.image_service.prepare_pass_images(temp_dir)
                logger.info("Images copied")

                # 3
                ManifestService.create_manifest_file(temp_dir)
                logger.info("Manifest created")

                # 4
                signing_svc = SigningService(temp_dir)
                signing_svc.sign()
                logger.info("Manifest signed")

                # 5
                pkg_svc = PackageService(temp_dir)
                pkpass_file = pkg_svc.package(custom_filename=filename)
                logger.info(f"PKPASS created: {pkpass_file}")

                return pkpass_file

        except Exception:
            logger.exception("generate_pkpass FAILED")
            raise