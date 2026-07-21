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

    def generate(self, data: LaundryPassData, serial_number: Optional[str] = None) -> Path:
        """Generates pass.json file from LaundryPassData schema."""
        if self.template.exists():
            with open(self.template, "r", encoding="utf-8") as f:
                template = json.load(f)
        else:
            template = {
                "formatVersion": 1,
                "foregroundColor": "rgb(255, 255, 255)",
                "backgroundColor": "rgb(15, 23, 42)",
                "labelColor": "rgb(148, 163, 184)"
            }

        template["passTypeIdentifier"] = settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER
        template["teamIdentifier"] = settings.APPLE_WALLET_TEAM_IDENTIFIER
        template["organizationName"] = settings.APP_NAME

        template["serialNumber"] = serial_number or f"PASS-{uuid.uuid4().hex[:8].upper()}"
        template["description"] = data.package_name
        template["logoText"] = data.package_name

        template["barcode"] = {
            "format": "PKBarcodeFormatQR",
            "message": data.qr_data,
            "messageEncoding": "iso-8859-1"
        }

        template["generic"] = {
            "primaryFields": [
                {
                    "key": "customer",
                    "label": "Customer",
                    "value": data.customer_name
                }
            ],
            "secondaryFields": [
                {
                    "key": "package",
                    "label": "Package / Order",
                    "value": data.package_name
                }
            ],
            "auxiliaryFields": [
                {
                    "key": "balance",
                    "label": "Balance",
                    "value": data.remaining_balance
                }
            ],
            "backFields": [
                {
                    "key": "expiry",
                    "label": "Expiry",
                    "value": data.expiry_date or "N/A"
                }
            ]
        }

        output_file = self.output / "pass.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=4, ensure_ascii=False)

        return output_file

    def generate_pkpass(self, pass_data: LaundryPassData, serial_number: Optional[str] = None) -> Path:
        """Complete workflow: generate pass.json, images, manifest, signature, and zip into .pkpass."""
        s_num = serial_number or f"PASS-{uuid.uuid4().hex[:8].upper()}"
        filename = f"pass_{s_num}.pkpass"
        output_base = Path(settings.APPLE_WALLET_GENERATED_PATH)

        with temporary_directory(output_base, prefix=s_num) as temp_dir:
            # 1. Generate pass.json
            self.output = temp_dir
            self.generate(pass_data, serial_number=s_num)

            # 2. Add Images
            self.image_service.prepare_pass_images(temp_dir)

            # 3. Create Manifest
            manifest_path = ManifestService.create_manifest_file(temp_dir)

            # 4. Sign Manifest
            signing_svc = SigningService(temp_dir)
            signing_svc.sign()

            # 5. Zip into .pkpass
            pkg_svc = PackageService(temp_dir)
            pkpass_file = pkg_svc.package(custom_filename=filename)

            return pkpass_file
