import logging
from typing import Any, Optional
from googleapiclient.discovery import build
from app.services.google_wallet.auth_service import GoogleWalletAuthService

logger = logging.getLogger(__name__)

_cached_client: Optional[Any] = None

def get_google_wallet_client(force_refresh: bool = False) -> Any:
    """
    Returns a cached Google Wallet REST API client (walletobjects v1).
    Isolated from Apple Wallet logic.
    """
    global _cached_client
    if _cached_client and not force_refresh:
        return _cached_client

    logger.info("[GoogleWallet] START Client Initialization")
    try:
        credentials = GoogleWalletAuthService.get_credentials()
        client = build("walletobjects", "v1", credentials=credentials, cache_discovery=False)
        _cached_client = client
        logger.info("[GoogleWallet] SUCCESS Client Initialization | service=walletobjects:v1")
        return client
    except Exception as e:
        logger.error(f"[GoogleWallet] FAILURE Client Initialization | reason={str(e)}")
        raise
