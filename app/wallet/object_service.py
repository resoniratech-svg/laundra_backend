import logging
from typing import Dict, Any, Optional
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.wallet.client import get_wallet_client, execute_with_retry
from app.wallet.exceptions import WalletObjectError

logger = logging.getLogger("google_wallet")

def build_object_payload(
    customer_package_id: str,
    customer_name: str,
    package_name: str,
    company_name: str = "Laundra Laundry",
    remaining_balance: float = 0.0,
    remaining_quantity: Optional[int] = None,
    expiry_date_str: str = "N/A",
    status: str = "ACTIVE",
    secure_token: str = ""
) -> Dict[str, Any]:
    """
    Constructs the Generic Object payload representing an individual customer's package.
    """
    issuer_id = settings.GOOGLE_WALLET_ISSUER_ID
    class_id = settings.GOOGLE_WALLET_CLASS_ID
    
    clean_id = str(customer_package_id).replace("-", "")
    object_id = f"{issuer_id}.customer_{clean_id}"

    balance_display = f"QR {remaining_balance:.2f}" if remaining_balance > 0 else f"{remaining_quantity or 0} Items"
    quantity_display = f"{remaining_quantity} items left" if remaining_quantity is not None else "Unlimited"

    return {
        "id": object_id,
        "classId": class_id,
        "state": "ACTIVE" if status.upper() == "ACTIVE" else "EXPIRED",
        "logo": {
            "sourceUri": {
                "uri": "https://raw.githubusercontent.com/google-pay/wallet-samples/main/generic-pass/logo.png"
            },
            "contentDescription": {
                "defaultValue": {
                    "language": "en-US",
                    "value": "Laundra Laundry Logo"
                }
            }
        },
        "cardTitle": {
            "defaultValue": {
                "language": "en-US",
                "value": company_name
            }
        },
        "header": {
            "defaultValue": {
                "language": "en-US",
                "value": f"{customer_name} - {package_name}"
            }
        },
        "textModulesData": [
            {
                "id": "balance",
                "header": "BALANCE",
                "body": balance_display
            },
            {
                "id": "remaining_orders",
                "header": "ITEMS REMAINING",
                "body": quantity_display
            },
            {
                "id": "expiry_date",
                "header": "EXPIRY DATE",
                "body": expiry_date_str
            },
            {
                "id": "status",
                "header": "STATUS",
                "body": status.upper()
            }
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": secure_token or str(customer_package_id),
            "alternateText": secure_token[:12] if secure_token else str(customer_package_id)[:12]
        },
        "hexBackgroundColor": "#1E293B"
    }

def create_wallet_object(
    customer_package_id: str,
    customer_name: str,
    package_name: str,
    company_name: str = "Laundra Laundry",
    remaining_balance: float = 0.0,
    remaining_quantity: Optional[int] = None,
    expiry_date_str: str = "N/A",
    status: str = "ACTIVE",
    secure_token: str = ""
) -> Dict[str, Any]:
    """
    Creates or updates a Google Wallet Object for a customer package with retry & logging.
    """
    object_payload = build_object_payload(
        customer_package_id=customer_package_id,
        customer_name=customer_name,
        package_name=package_name,
        company_name=company_name,
        remaining_balance=remaining_balance,
        remaining_quantity=remaining_quantity,
        expiry_date_str=expiry_date_str,
        status=status,
        secure_token=secure_token
    )
    
    client = get_wallet_client()
    object_id = object_payload["id"]

    try:
        existing = execute_with_retry(lambda: client.genericobject().get(resourceId=object_id).execute())
        logger.info(f"[INFO] Wallet Object Verified/Fetched: {object_id}")
        return {
            "status": "EXISTS",
            "object_id": existing.get("id", object_id),
            "payload": existing
        }
    except HttpError as err:
        if err.resp.status == 404:
            try:
                created = execute_with_retry(lambda: client.genericobject().insert(body=object_payload).execute())
                logger.info(f"[INFO] Wallet Object Created: {object_id}")
                return {
                    "status": "CREATED",
                    "object_id": created.get("id", object_id),
                    "payload": created
                }
            except HttpError:
                logger.info(f"[INFO] Wallet Object Prepared for JWT Inclusion: {object_id}")
                return {
                    "status": "JWT_READY",
                    "object_id": object_id,
                    "payload": object_payload
                }
        else:
            logger.error(f"[ERROR] Google Wallet API Failed creating object {object_id}: {err}")
            raise WalletObjectError(f"Google Wallet API Error: {err}")
    except Exception as ex:
        logger.info(f"[INFO] Wallet Object Ready for JWT: {object_id}")
        return {
            "status": "JWT_READY",
            "object_id": object_id,
            "payload": object_payload
        }
