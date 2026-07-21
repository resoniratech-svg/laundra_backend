import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings
from app.services.apple_wallet.utils import parse_pkcs12_certificate, parse_x509_certificate

logger = logging.getLogger("apple_wallet.certificate_service")

class CertificateService:
    """Service for managing Apple Developer Pass Type Certificates and WWDR CA."""

    def __init__(
        self,
        p12_path: Optional[Path] = None,
        p12_password: Optional[str] = None,
        wwdr_path: Optional[Path] = None
    ):
        self.p12_path = p12_path or Path(settings.APPLE_WALLET_CERTIFICATE_PATH)
        self.p12_password = p12_password or settings.APPLE_WALLET_CERTIFICATE_PASSWORD
        self.wwdr_path = wwdr_path or Path(settings.APPLE_WALLET_WWDR_CERTIFICATE_PATH)

    def get_credentials(self) -> Tuple[Optional[rsa.RSAPrivateKey], Optional[x509.Certificate], list]:
        """Loads key and cert chain from pass.p12."""
        return parse_pkcs12_certificate(self.p12_path, self.p12_password)

    def get_wwdr_certificate(self) -> Optional[x509.Certificate]:
        """Loads Apple WWDR CA certificate from AppleWWDRCA.cer."""
        return parse_x509_certificate(self.wwdr_path)

    def is_certificate_configured(self) -> bool:
        """Returns True if valid pass key & cert are loaded."""
        key, cert, _ = self.get_credentials()
        return key is not None and cert is not None

    def is_wwdr_configured(self) -> bool:
        """Returns True if WWDR CA cert is loaded."""
        return self.get_wwdr_certificate() is not None

    def validate_certificate(self) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []
        now = datetime.now(timezone.utc)

        if not self.p12_path.exists():
            errors.append(f"Pass certificate missing at {self.p12_path}")
        else:
            key, cert, _ = self.get_credentials()
            if not key or not cert:
                errors.append(f"Failed to parse PKCS#12 certificate from {self.p12_path}")
            else:
                try:
                    expiry = cert.not_valid_after_utc
                except AttributeError:
                    expiry = cert.not_valid_after.replace(tzinfo=timezone.utc)

                if expiry < now:
                    errors.append(f"Pass certificate expired on {expiry.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                elif expiry < now + timedelta(days=30):
                    warnings.append(f"Pass certificate expires soon: {expiry.strftime('%Y-%m-%d %H:%M:%S UTC')}")

                subject_str = cert.subject.rfc4514_string()
                logger.info(f"Pass Certificate Subject: {subject_str}")

                if settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER and settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER not in subject_str:
                    warnings.append(
                        f"Pass Type ID '{settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER}' not explicitly matched in certificate subject"
                    )

                if settings.APPLE_WALLET_TEAM_IDENTIFIER and settings.APPLE_WALLET_TEAM_IDENTIFIER not in subject_str:
                    warnings.append(
                        f"Team ID '{settings.APPLE_WALLET_TEAM_IDENTIFIER}' not explicitly matched in certificate subject"
                    )

        if not self.wwdr_path.exists():
            warnings.append(f"Apple WWDR CA certificate missing at {self.wwdr_path}")
        else:
            wwdr_cert = self.get_wwdr_certificate()
            if not wwdr_cert:
                warnings.append(f"Failed to parse WWDR CA certificate at {self.wwdr_path}")
            else:
                try:
                    wwdr_expiry = wwdr_cert.not_valid_after_utc
                except AttributeError:
                    wwdr_expiry = wwdr_cert.not_valid_after.replace(tzinfo=timezone.utc)

                if wwdr_expiry < now:
                    errors.append(f"Apple WWDR CA certificate expired on {wwdr_expiry.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        is_valid = len(errors) == 0
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
        }
