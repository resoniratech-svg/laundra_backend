import logging
import time
from typing import Callable, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.wallet.auth import get_google_wallet_credentials

logger = logging.getLogger("google_wallet")

def get_wallet_client():
    """
    Build and return an authenticated Google Wallet API client instance.
    """
    credentials = get_google_wallet_credentials()
    client = build("walletobjects", "v1", credentials=credentials)
    return client

def execute_with_retry(api_func: Callable[[], Any], max_attempts: int = 3, initial_delay: float = 1.0) -> Any:
    """
    Phase 15: Retry Mechanism for Google Wallet API Calls
    Retries failed Google Wallet API calls up to `max_attempts` times with exponential backoff.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = api_func()
            return result
        except HttpError as http_err:
            last_exception = http_err
            if http_err.resp.status in [500, 502, 503, 504, 429]:
                logger.warning(f"[RETRY {attempt}/{max_attempts}] Google Wallet API temporary error {http_err.resp.status}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                # Client errors (400, 404, 403) should fail fast without retrying
                raise http_err
        except Exception as ex:
            last_exception = ex
            logger.warning(f"[RETRY {attempt}/{max_attempts}] Network/Unexpected error: {ex}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2

    logger.error(f"[ERROR] Google Wallet API Failed after {max_attempts} attempts. Details: {last_exception}")
    raise last_exception

def test_wallet_authentication() -> dict:
    """
    Test Google Wallet Service Account authentication by fetching live credentials.
    """
    from google.auth.transport.requests import Request
    credentials = get_google_wallet_credentials()
    
    request = Request()
    credentials.refresh(request)
    
    client = get_wallet_client()
    
    logger.info("[INFO] Google Wallet Authentication Verified Successfully.")
    return {
        "status": "SUCCESS",
        "service_account_email": credentials.service_account_email,
        "project_id": credentials.project_id,
        "token_acquired": bool(credentials.token),
        "token_type": "Bearer",
        "client_initialized": client is not None
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        res = test_wallet_authentication()
        print("[SUCCESS] Google Wallet Authentication Successful!")
        print(f"   Service Account: {res['service_account_email']}")
    except Exception as e:
        print(f"[FAILED] Google Wallet Authentication Failed: {e}")
