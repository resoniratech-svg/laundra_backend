import logging
from typing import Dict, Any, Optional
from googleapiclient.errors import HttpError
from app.core.config import settings
from app.services.google_wallet.client import get_google_wallet_client

logger = logging.getLogger(__name__)

class GoogleWalletClassService:
    @staticmethod
    def get_class_id() -> str:
        """
        Returns deterministic Generic Class ID in standard format:
        {ISSUER_ID}.{CLASS_SUFFIX}
        """
        class_id = settings.GOOGLE_WALLET_CLASS_ID
        if not class_id or not settings.GOOGLE_WALLET_ISSUER_ID:
            raise ValueError(
                "GOOGLE_WALLET_ISSUER_ID is not configured. Please set GOOGLE_WALLET_ISSUER_ID in .env."
            )
        return class_id

    @classmethod
    def build_generic_class_payload(cls, class_id: str) -> Dict[str, Any]:
        """
        Builds minimal, production-safe GenericClass template for Laundra Prepaid Packages.
        Template only — contains NO customer-specific information.
        """
        return {
            "id": class_id,
            "issuerName": "Laundra Laundry Services",
            "reviewStatus": "underReview"
        }

    @classmethod
    def get_or_create_generic_class(cls, client: Optional[Any] = None) -> Dict[str, Any]:
        """
        Idempotently checks if GenericClass exists.
        If missing (404), creates it.
        If permission or auth error occurs (403, 401), raises the true error instead of assuming missing.
        """
        class_id = cls.get_class_id()
        if not client:
            client = get_google_wallet_client()

        logger.info(f"[GoogleWallet] START Class Lookup | class_id={class_id}")

        # 1. Check if class exists
        try:
            existing_class = client.genericclass().get(resourceId=class_id).execute()
            logger.info(f"[GoogleWallet] SUCCESS Class Found | class_id={class_id}")
            return {
                "status": "EXISTS",
                "class_id": class_id,
                "data": existing_class
            }
        except HttpError as err:
            if err.resp.status == 404:
                logger.info(f"[GoogleWallet] Class NOT FOUND (404). Proceeding to create | class_id={class_id}")
            else:
                logger.error(
                    f"[GoogleWallet] FAILURE Class Lookup | class_id={class_id} | status={err.resp.status} | reason={err}"
                )
                raise
        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Class Lookup | class_id={class_id} | reason={str(e)}")
            raise

        # 2. Class does not exist (404 confirmed) — Create it
        logger.info(f"[GoogleWallet] START Class Creation | class_id={class_id}")
        payload = cls.build_generic_class_payload(class_id)

        try:
            created_class = client.genericclass().insert(body=payload).execute()
            logger.info(f"[GoogleWallet] SUCCESS Class Created | class_id={class_id}")
            return {
                "status": "CREATED",
                "class_id": class_id,
                "data": created_class
            }
        except Exception as e:
            logger.error(f"[GoogleWallet] FAILURE Class Creation | class_id={class_id} | reason={str(e)}")
            raise
