import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from cryptography.hazmat.primitives import serialization
from sqlalchemy.orm import Session

import httpx

from app.core.config import settings
from app.services.apple_wallet.utils import parse_pkcs12_certificate
from app.models.apple_device_registration import AppleDeviceRegistration

logger = logging.getLogger("apple_wallet.apns_service")

class APNsService:
    """
    Production-ready Apple Push Notification Service (APNs) client over HTTP/2.
    Sends silent background push notifications to registered iOS devices
    to trigger automatic PassKit Apple Wallet pass updates.
    """

    def __init__(self):
        self.apns_topic = getattr(settings, "APPLE_WALLET_PASS_TYPE_IDENTIFIER", "pass.com.laundry.wallet")
        self.use_sandbox = getattr(settings, "APNS_SANDBOX", False)
        
        # APNs endpoints
        if self.use_sandbox:
            self.apns_host = "api.sandbox.push.apple.com"
        else:
            self.apns_host = "api.push.apple.com"

        self.p12_path = Path(settings.APPLE_WALLET_CERTIFICATE_PATH)
        self.p12_password = settings.APPLE_WALLET_CERTIFICATE_PASSWORD
        self._cert_path: Optional[Path] = None
        self._key_path: Optional[Path] = None

    def _ensure_pem_credentials(self) -> bool:
        """Extracts and caches PEM certificate and private key from PKCS#12 bundle."""
        if self._cert_path and self._key_path and self._cert_path.exists() and self._key_path.exists():
            return True

        if not self.p12_path.exists():
            logger.error(f"[APNs] Certificate file missing at {self.p12_path}")
            return False

        try:
            cache_dir = self.p12_path.parent / ".pem_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            cert_file = cache_dir / "apns_cert.pem"
            key_file = cache_dir / "apns_key.pem"

            # Check if cached files exist and are non-empty
            if cert_file.exists() and key_file.exists() and cert_file.stat().st_size > 0 and key_file.stat().st_size > 0:
                self._cert_path = cert_file
                self._key_path = key_file
                return True

            key, cert, add_certs = parse_pkcs12_certificate(self.p12_path, self.p12_password)
            if not key or not cert:
                logger.error("[APNs] Failed to parse private key or certificate from P12 file.")
                return False

            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()
            )

            cert_file.write_bytes(cert_pem)
            key_file.write_bytes(key_pem)

            self._cert_path = cert_file
            self._key_path = key_file
            logger.info(f"[APNs] Successfully cached PEM certificates at {cache_dir}")
            return True

        except Exception as e:
            logger.error(f"[APNs] Error preparing PEM credentials: {e}")
            return False

    def send_push_notification(self, push_token: str) -> Dict[str, Any]:
        """
        Sends an empty APNs notification payload ({}) over HTTP/2 to a registered iOS device.
        Per Apple PassKit specification:
        - POST /3/device/{push_token}
        - Header 'apns-topic': passTypeIdentifier
        - Body: {}
        """
        print("[APNS DEBUG] ABOUT TO SEND PUSH", flush=True)
        print(f"[APNS DEBUG] token={push_token}", flush=True)

        if not push_token:
            return {"success": False, "reason": "empty_token", "expired": False}

        if not self._ensure_pem_credentials():
            return {"success": False, "reason": "credentials_failed", "expired": False}

        url = f"https://{self.apns_host}/3/device/{push_token}"
        headers = {
            "apns-topic": self.apns_topic,
            "apns-push-type": "background",
            "apns-expiration": "0"
        }
        # Apple PassKit spec requires empty JSON payload {}
        body = "{}"

        logger.info(f"[APNs] Sending HTTP/2 push to token: {push_token[:10]}... (Host: {self.apns_host}, Topic: {self.apns_topic})")

        try:
            with httpx.Client(
                http2=True,
                cert=(str(self._cert_path), str(self._key_path)),
                timeout=10.0
            ) as client:
                response = client.post(url, headers=headers, content=body)

            print(f"[APNS DEBUG] APNS STATUS={response.status_code}", flush=True)
            print(f"[APNS DEBUG] APNS RESPONSE={response.text}", flush=True)

            if response.status_code == 200:
                apns_id = response.headers.get("apns-id", "N/A")
                logger.info(f"[APNs] Push SUCCESS (200 OK) for token {push_token[:10]}... [apns-id: {apns_id}]")
                return {"success": True, "reason": "ok", "expired": False, "apns_id": apns_id}
            
            elif response.status_code in [400, 410]:
                # 410 Unregistered or 400 BadDeviceToken -> Token is no longer valid or pass removed
                resp_json = {}
                try:
                    resp_json = response.json()
                except Exception:
                    pass
                reason = resp_json.get("reason", "Unregistered")
                logger.warning(f"[APNs] Token EXPIRED/INVALID ({response.status_code} {reason}) for token {push_token[:10]}...")
                return {"success": False, "reason": reason, "expired": True}
            
            else:
                logger.error(f"[APNs] Push FAILED ({response.status_code}): {response.text}")
                return {"success": False, "reason": f"HTTP_{response.status_code}", "expired": False}

        except Exception as e:
            print(f"[APNS DEBUG] PUSH FAILED: {e}", flush=True)
            logger.error(f"[APNs] Network/HTTP2 error sending push to {push_token[:10]}...: {e}")
            return {"success": False, "reason": str(e), "expired": False}

    def notify_devices_for_pass(self, db: Session, serial_number: str) -> Dict[str, Any]:
        """
        Retrieves all registered iOS devices for the given pass serial number,
        dispatches APNs push notifications, and automatically cleans up expired tokens from DB.
        """
        print("[APNS DEBUG] ENTER notify_devices_for_pass", flush=True)
        print(f"[APNS DEBUG] serial_number={serial_number}", flush=True)
        print("[APNS DEBUG] BEFORE querying registered devices", flush=True)

        registrations = db.query(AppleDeviceRegistration).filter(
            AppleDeviceRegistration.serial_number == serial_number
        ).all()

        print(f"[APNS DEBUG] registered device count={len(registrations)}", flush=True)
        for r in registrations:
            print(f"[APNS DEBUG] device={r.device_library_identifier}", flush=True)
            print(f"[APNS DEBUG] token={r.push_token}", flush=True)
            print(f"[APNS DEBUG] pass_type={r.pass_type_identifier}", flush=True)

        if not registrations:
            print("[APNS DEBUG] NO REGISTERED DEVICES FOUND", flush=True)
            logger.info(f"[APNs] No registered iOS devices found for serial_number: {serial_number}")
            summary = {"total": 0, "sent": 0, "expired_removed": 0}
            print(f"[APNS DEBUG] SUMMARY={summary}", flush=True)
            print("[APNS DEBUG] EXIT notify_devices_for_pass", flush=True)
            return summary

        logger.info(f"[APNs] Found {len(registrations)} registered device(s) for pass serial_number: {serial_number}")
        
        sent_count = 0
        removed_count = 0

        for reg in registrations:
            res = self.send_push_notification(reg.push_token)
            if res.get("success"):
                sent_count += 1
            elif res.get("expired"):
                logger.info(f"[APNs] Removing expired registration ID {reg.id} for serial_number {serial_number}")
                db.delete(reg)
                removed_count += 1

        if removed_count > 0:
            try:
                db.commit()
            except Exception as e:
                logger.error(f"[APNs] Failed to commit removal of expired device registrations: {e}")
                db.rollback()

        summary = {
            "total": len(registrations),
            "sent": sent_count,
            "expired_removed": removed_count
        }
        logger.info(f"[APNs] Pass update notification summary for {serial_number}: {summary}")
        print(f"[APNS DEBUG] SUMMARY={summary}", flush=True)
        print("[APNS DEBUG] EXIT notify_devices_for_pass", flush=True)
        return summary
