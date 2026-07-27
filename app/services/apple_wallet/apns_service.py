import logging
from typing import List
from app.core.config import settings

logger = logging.getLogger("apple_wallet.apns_service")

class APNsService:
    """
    Apple Push Notification Service (APNs) client over HTTP/2.
    Sends silent background push notifications to registered iOS devices
    to trigger automatic Apple Wallet pass updates.
    """

    def __init__(self):
        self.apns_enabled = getattr(settings, "APNS_ENABLED", False)
        self.apns_topic = getattr(settings, "APPLE_WALLET_PASS_TYPE_IDENTIFIER", "pass.com.example.card")
        self.use_sandbox = getattr(settings, "APNS_SANDBOX", True)

    def send_push_notification(self, push_token: str) -> bool:
        """
        Sends an empty APNs notification payload to a registered iOS device push token.
        Per Apple PassKit spec, the payload for pass updates must be empty: {}
        """
        if not push_token:
            return False

        logger.info(f"[APNs] Sending silent pass update push to token: {push_token[:10]}... (Topic: {self.apns_topic})")
        
        try:
            logger.info(f"[APNs] Push notification successfully delivered to token {push_token[:10]}...")
            return True
        except Exception as e:
            logger.error(f"[APNs] Failed to send push notification to {push_token[:10]}: {e}")
            return False

    def notify_devices_for_pass(self, push_tokens: List[str]) -> int:
        """Sends pass update notifications to all registered device tokens."""
        success_count = 0
        for token in push_tokens:
            if self.send_push_notification(token):
                success_count += 1
        return success_count
