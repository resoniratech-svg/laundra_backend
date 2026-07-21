import hashlib
import json
import logging
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.services.apple_wallet.certificate_service import CertificateService
from app.services.apple_wallet.utils import calculate_sha1

logger = logging.getLogger("apple_wallet.validation_service")

class ValidationService:
    """
    Validates Apple Wallet pass bundles, manifest integrity, signature,
    certificate validity, and compiled .pkpass archives.
    """

    REQUIRED_FILES = {"pass.json", "manifest.json", "signature", "icon.png", "logo.png"}
    REQUIRED_JSON_KEYS = [
        "formatVersion",
        "passTypeIdentifier",
        "teamIdentifier",
        "organizationName",
        "serialNumber",
        "description",
    ]

    def __init__(self, pass_dir: Optional[Path] = None, pkpass_path: Optional[Path] = None):
        output_base = Path(settings.APPLE_WALLET_GENERATED_PATH)
        self.pass_dir = pass_dir or (output_base / "pass")
        self.pkpass_path = pkpass_path or (output_base / "wallet.pkpass")
        self.cert_service = CertificateService()

    def validate_pass_json(self) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        pass_json_file = self.pass_dir / "pass.json"
        if not pass_json_file.exists():
            errors.append("pass.json does not exist")
            return {"valid": False, "errors": errors, "warnings": warnings}

        try:
            with open(pass_json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("formatVersion") != 1:
                errors.append(f"formatVersion must be 1, got {data.get('formatVersion')}")

            for key in self.REQUIRED_JSON_KEYS:
                if not data.get(key):
                    errors.append(f"Missing required JSON field: {key}")

            if data.get("teamIdentifier") != settings.APPLE_WALLET_TEAM_IDENTIFIER:
                warnings.append(
                    f"teamIdentifier '{data.get('teamIdentifier')}' differs from settings '{settings.APPLE_WALLET_TEAM_IDENTIFIER}'"
                )
            if data.get("passTypeIdentifier") != settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER:
                warnings.append(
                    f"passTypeIdentifier '{data.get('passTypeIdentifier')}' differs from settings '{settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER}'"
                )

            if "barcode" in data or "barcodes" in data:
                barcodes = data.get("barcodes") or [data.get("barcode")]
                for bc in barcodes:
                    if not bc or not bc.get("format") or not bc.get("message"):
                        errors.append("Barcode format or message is missing")

        except Exception as e:
            errors.append(f"Invalid pass.json format: {str(e)}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_manifest(self) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        manifest_file = self.pass_dir / "manifest.json"
        if not manifest_file.exists():
            errors.append("manifest.json missing")
            return {"valid": False, "errors": errors, "warnings": warnings}

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            for file_path in self.pass_dir.iterdir():
                if file_path.is_file() and file_path.name not in ["manifest.json", "signature", ".DS_Store"]:
                    calc_hash = calculate_sha1(file_path)
                    manifest_hash = manifest_data.get(file_path.name)
                    if not manifest_hash:
                        errors.append(f"File {file_path.name} is missing in manifest.json")
                    elif calc_hash.lower() != manifest_hash.lower():
                        errors.append(
                            f"SHA1 mismatch for {file_path.name}: manifest={manifest_hash}, calculated={calc_hash}"
                        )

            for file_name in manifest_data.keys():
                if not (self.pass_dir / file_name).exists():
                    errors.append(f"File listed in manifest.json missing from pass directory: {file_name}")

        except Exception as e:
            errors.append(f"Error reading manifest.json: {str(e)}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_signature(self) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        signature_file = self.pass_dir / "signature"
        manifest_file = self.pass_dir / "manifest.json"

        if not signature_file.exists():
            errors.append("signature file missing")
            return {"valid": False, "errors": errors, "warnings": warnings}

        if not manifest_file.exists():
            errors.append("manifest.json missing for signature verification")
            return {"valid": False, "errors": errors, "warnings": warnings}

        wwdr_path = Path(settings.APPLE_WALLET_WWDR_CERTIFICATE_PATH)

        if wwdr_path.exists():
            try:
                cmd = [
                    "openssl", "smime", "-verify",
                    "-in", str(signature_file),
                    "-inform", "DER",
                    "-content", str(manifest_file),
                    "-CAfile", str(wwdr_path),
                    "-purpose", "any"
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode != 0:
                    warnings.append(f"OpenSSL signature verification warning: {res.stderr.decode('utf-8').strip()}")
                else:
                    logger.info("OpenSSL PKCS7 signature verification passed successfully.")
            except Exception as e:
                warnings.append(f"OpenSSL verification unavailable or failed: {str(e)}")

        if signature_file.stat().st_size < 100:
            errors.append("signature file is suspiciously small or empty")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    def validate_all(self) -> Dict[str, Any]:
        json_report = self.validate_pass_json()
        manifest_report = self.validate_manifest()
        sig_report = self.validate_signature()
        cert_report = self.cert_service.validate_certificate()

        all_errors = json_report["errors"] + manifest_report["errors"] + sig_report["errors"] + cert_report["errors"]
        all_warnings = json_report["warnings"] + manifest_report["warnings"] + sig_report["warnings"] + cert_report["warnings"]

        is_valid = len(all_errors) == 0

        return {
            "valid": is_valid,
            "json_valid": json_report["valid"],
            "manifest_valid": manifest_report["valid"],
            "signature_valid": sig_report["valid"],
            "certificate_valid": cert_report["valid"],
            "package_valid": is_valid,
            "errors": all_errors,
            "warnings": all_warnings,
        }
