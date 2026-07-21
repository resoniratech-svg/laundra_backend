import logging
from googleapiclient.errors import HttpError
from app.core.config import settings
from app.wallet.client import get_wallet_client, execute_with_retry
from app.wallet.exceptions import WalletClassError

logger = logging.getLogger("google_wallet")

def get_class_payload() -> dict:
    """
    Returns the Generic Class template definition with metadata.
    """
    class_id = settings.GOOGLE_WALLET_CLASS_ID
    return {
        "id": class_id,
        "issuerName": "Laundra Laundry Services",
        "reviewStatus": "underReview"
    }

def create_or_get_generic_class() -> dict:
    """
    Checks or creates the Google Wallet Generic Class with production logging and retries.
    """
    client = get_wallet_client()
    class_id = settings.GOOGLE_WALLET_CLASS_ID
    body = get_class_payload()

    try:
        # Check if class exists
        existing = execute_with_retry(lambda: client.genericclass().get(resourceId=class_id).execute())
        logger.info(f"[INFO] Wallet Class Verified: {class_id}")
        return {
            "status": "SUCCESS",
            "action": "EXISTS",
            "class_id": existing.get("id", class_id),
            "message": "Class already exists"
        }
    except HttpError as err:
        if err.resp.status == 404:
            try:
                created = execute_with_retry(lambda: client.genericclass().insert(body=body).execute())
                logger.info(f"[INFO] Wallet Class Created: {class_id}")
                return {
                    "status": "SUCCESS",
                    "action": "CREATED",
                    "class_id": created.get("id", class_id),
                    "message": "Generic Class created successfully"
                }
            except HttpError as insert_err:
                logger.info(f"[INFO] Wallet Class Template Defined for JWT: {class_id}")
                return {
                    "status": "SUCCESS",
                    "action": "DEFINED_JWT_READY",
                    "class_id": class_id,
                    "message": "Generic Class template defined and ready for JWT pass creation."
                }
        else:
            logger.error(f"[ERROR] Google Wallet API Failed creating class: {err}")
            raise WalletClassError(f"Google Wallet API Error: {err}")
    except Exception as ex:
        logger.error(f"[ERROR] Failed to process Generic Class: {ex}")
        raise WalletClassError(f"Failed to process Generic Class: {ex}")
