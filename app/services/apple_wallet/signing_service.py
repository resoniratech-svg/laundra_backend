import logging
from pathlib import Path
import subprocess
import tempfile
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from app.core.config import settings
from app.services.apple_wallet.utils import parse_pkcs12_certificate, parse_x509_certificate

logger = logging.getLogger("apple_wallet.signing_service")

class SigningService:
    """Creates Apple's PKCS#7 signature file for Apple Wallet passes."""

    def __init__(self, pass_directory: Path):
        self.pass_directory = pass_directory
        self.manifest = pass_directory / "manifest.json"
        self.signature = pass_directory / "signature"

    def sign(self) -> Path:
        p12_path = Path(settings.APPLE_WALLET_CERTIFICATE_PATH)
        wwdr_path = Path(settings.APPLE_WALLET_WWDR_CERTIFICATE_PATH)
        password = settings.APPLE_WALLET_CERTIFICATE_PASSWORD

        if not self.manifest.exists():
            raise FileNotFoundError(f"Manifest file missing for signing: {self.manifest}")

        if p12_path.exists() and wwdr_path.exists():
            try:
                sig_bytes = self._sign_with_openssl(p12_path, password, wwdr_path, self.manifest)
                self.signature.parent.mkdir(parents=True, exist_ok=True)
                self.signature.write_bytes(sig_bytes)
                logger.info("Successfully signed manifest.json with OpenSSL PKCS7 S/MIME signature (-md sha1).")
                return self.signature
            except Exception as e:
                logger.warning(f"OpenSSL signing failed: {e}. Attempting Python cryptography SHA-1 fallback.")

        # Cryptography fallback using SHA1
        key, cert, add_certs = parse_pkcs12_certificate(p12_path, password)
        wwdr_cert = parse_x509_certificate(wwdr_path)

        if key and cert:
            try:
                builder = pkcs7.PKCS7SignatureBuilder()
                manifest_data = self.manifest.read_bytes()
                builder = builder.set_data(manifest_data)
                builder = builder.add_signer(cert, key, hashes.SHA256())
                if wwdr_cert:
                    builder = builder.add_certificate(wwdr_cert)
                for extra in add_certs:
                    builder = builder.add_certificate(extra)
                options = [pkcs7.PKCS7Options.DetachedSignature]
                sig_bytes = builder.sign(serialization.Encoding.DER, options)
                self.signature.parent.mkdir(parents=True, exist_ok=True)
                self.signature.write_bytes(sig_bytes)
                logger.info("Successfully signed manifest.json with Python cryptography (SHA-256).")
                return self.signature
            except Exception as e:
                logger.error(f"Cryptography signing error: {e}")
                raise RuntimeError(f"Cryptographic signing failed: {e}")

        raise RuntimeError("Certificate or private key unconfigured. Cannot sign pass.")

    def _sign_with_openssl(self, p12_path: Path, password: str, wwdr_path: Path, manifest_path: Path) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cert_pem = tmp / "signerCert.pem"
            key_pem = tmp / "signerKey.pem"
            out_sig = tmp / "signature"

            cmd_cert = [
                "openssl", "pkcs12", "-in", str(p12_path), "-clcerts", "-nokeys",
                "-out", str(cert_pem), "-passin", f"pass:{password}", "-legacy"
            ]
            res1 = subprocess.run(cmd_cert, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res1.returncode != 0:
                cmd_cert.remove("-legacy")
                subprocess.run(cmd_cert, check=True)

            cmd_key = [
                "openssl", "pkcs12", "-in", str(p12_path), "-nocerts", "-nodes",
                "-out", str(key_pem), "-passin", f"pass:{password}", "-legacy"
            ]
            res2 = subprocess.run(cmd_key, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res2.returncode != 0:
                cmd_key.remove("-legacy")
                subprocess.run(cmd_key, check=True)

            cmd_sign = [
                "openssl", "smime", "-binary", "-sign",
                "-certfile", str(wwdr_path),
                "-signer", str(cert_pem),
                "-inkey", str(key_pem),
                "-in", str(manifest_path),
                "-out", str(out_sig),
                "-outform", "DER",
                "-md", "sha1"
            ]
            subprocess.run(cmd_sign, check=True)
            return out_sig.read_bytes()

    def sign_manifest(self, manifest_bytes: bytes) -> bytes:
        self.pass_directory.mkdir(parents=True, exist_ok=True)
        self.manifest.write_bytes(manifest_bytes)
        sig_path = self.sign()
        return sig_path.read_bytes()
