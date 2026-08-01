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
        Builds production-grade GenericClass template for Laundra Prepaid Packages.
        Matches exact reference design with dynamic multi-service support:
        Row 1: CUSTOMER
        Row 2: PACKAGE + COUPON COST
        Row 3: STATUS + SERVICE 1 LEFT
        Row 4..12: SERVICE 2..10 LEFT
        """
        row_templates = [
            {
                "oneItem": {
                    "item": {
                        "firstValue": {
                            "fields": [
                                {"fieldPath": "object.textModulesData['customer']"}
                            ]
                        }
                    }
                }
            },
            {
                "twoItems": {
                    "startItem": {
                        "firstValue": {
                            "fields": [
                                {"fieldPath": "object.textModulesData['package']"}
                            ]
                        }
                    },
                    "endItem": {
                        "firstValue": {
                            "fields": [
                                {"fieldPath": "object.textModulesData['coupon_cost']"}
                            ]
                        }
                    }
                }
            },
            {
                "twoItems": {
                    "startItem": {
                        "firstValue": {
                            "fields": [
                                {"fieldPath": "object.textModulesData['status']"}
                            ]
                        }
                    },
                    "endItem": {
                        "firstValue": {
                            "fields": [
                                {"fieldPath": "object.textModulesData['service_1']"}
                            ]
                        }
                    }
                }
            }
        ]

        # Dynamically add 2-per-row twoItems template rows for service_2 through service_11
        for i in range(2, 12, 2):
            s_start = f"service_{i}"
            s_end = f"service_{i+1}"
            row_templates.append({
                "twoItems": {
                    "startItem": {
                        "firstValue": {
                            "fields": [
                                {"fieldPath": f"object.textModulesData['{s_start}']"}
                            ]
                        }
                    },
                    "endItem": {
                        "firstValue": {
                            "fields": [
                                {"fieldPath": f"object.textModulesData['{s_end}']"}
                            ]
                        }
                    }
                }
            })

        return {
            "id": class_id,
            "issuerName": "Dry Cleaners",
            "reviewStatus": "underReview",
            "classTemplateInfo": {
                "cardTemplateOverride": {
                    "cardRowTemplateInfos": row_templates
                }
            }
        }

    @classmethod
    def get_or_create_generic_class(cls, client: Optional[Any] = None) -> Dict[str, Any]:
        """
        Idempotently checks if GenericClass exists.
        If missing (404), creates it.
        Patches existing class layout to support dynamic multi-service rows.
        """
        class_id = cls.get_class_id()
        if not client:
            client = get_google_wallet_client()

        logger.info(f"[GoogleWallet] START Class Lookup | class_id={class_id}")

        # 1. Check if class exists
        try:
            existing_class = client.genericclass().get(resourceId=class_id).execute()
            logger.info(f"[GoogleWallet] SUCCESS Class Found | class_id={class_id}")

            # Patch live class layout to ensure service_1 through service_10 template rows are registered
            try:
                payload = cls.build_generic_class_payload(class_id)
                existing_class = client.genericclass().patch(resourceId=class_id, body=payload).execute()
                logger.info(f"[GoogleWallet] SUCCESS Patched Class Layout for All Services | class_id={class_id}")
            except Exception as e_patch:
                logger.warning(f"[GoogleWallet] Warning patching class layout: {e_patch}")

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
