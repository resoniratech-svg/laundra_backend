import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from app.core.config import settings
from app.services.google_wallet.auth_service import GoogleWalletAuthService
from app.services.google_wallet.client import get_google_wallet_client
from app.services.google_wallet.class_service import GoogleWalletClassService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_setup():
    summary = {
        "config": "FAIL",
        "credential_file": "FAIL",
        "authentication": "FAIL",
        "wallet_api_client": "FAIL",
        "issuer_id": "N/A",
        "generic_class_id": "N/A",
        "generic_class": "FAIL",
        "final_result": "FAIL"
    }

    print("\n" + "="*60)
    print("      GOOGLE WALLET SETUP VERIFICATION (PHASE 1)")
    print("="*60 + "\n")

    # 1. Configuration check
    try:
        if not settings.GOOGLE_WALLET_ENABLED:
            print("[x] Configuration Error: GOOGLE_WALLET_ENABLED is False")
            return print_summary(summary)
            
        issuer_id = settings.GOOGLE_WALLET_ISSUER_ID
        if not issuer_id:
            print("[x] Configuration Error: GOOGLE_WALLET_ISSUER_ID is not configured in .env")
            return print_summary(summary)
            
        summary["config"] = "PASS"
        summary["issuer_id"] = issuer_id
        summary["generic_class_id"] = settings.GOOGLE_WALLET_CLASS_ID or f"{issuer_id}.{settings.GOOGLE_WALLET_CLASS_SUFFIX}"
        print(f"[OK] Configuration Loaded: Issuer ID={issuer_id} | Class ID={summary['generic_class_id']}")
    except Exception as e:
        print(f"[x] Configuration Failed: {e}")
        return print_summary(summary)

    # 2. Credential File Check
    try:
        cred_path = GoogleWalletAuthService.get_credentials_path()
        summary["credential_file"] = "PASS"
        print(f"[OK] Credential File Verified: {cred_path}")
    except Exception as e:
        print(f"[x] Credential File Missing/Invalid: {e}")
        return print_summary(summary)

    # 3. Authentication Check
    try:
        credentials = GoogleWalletAuthService.get_credentials()
        project_id = getattr(credentials, "project_id", "N/A")
        client_email = getattr(credentials, "service_account_email", "N/A")
        summary["authentication"] = "PASS"
        print(f"[OK] Authentication Successful: project_id={project_id} | client_email={client_email}")
    except Exception as e:
        print(f"[x] Authentication Failed: {e}")
        return print_summary(summary)

    # 4. Wallet API Client Check
    try:
        client = get_google_wallet_client(force_refresh=True)
        summary["wallet_api_client"] = "PASS"
        print("[OK] Google Wallet API Client Constructed (walletobjects:v1)")
    except Exception as e:
        print(f"[x] Wallet API Client Failed: {e}")
        return print_summary(summary)

    # 5. Generic Class Lookup & Creation
    try:
        res = GoogleWalletClassService.get_or_create_generic_class(client=client)
        status = res.get("status", "UNKNOWN")
        summary["generic_class"] = f"{status}"
        print(f"[OK] Generic Class Verification: Status={status} | Class ID={res.get('class_id')}")
        summary["final_result"] = "PASS"
    except Exception as e:
        print(f"[x] Generic Class Operations Failed: {e}")
        summary["generic_class"] = f"FAIL ({type(e).__name__})"
        return print_summary(summary)

    print_summary(summary)

def print_summary(s: dict):
    print("\n" + "="*60)
    print("GOOGLE WALLET SETUP VERIFICATION")
    print("="*60)
    print(f"Configuration       : {s['config']}")
    print(f"Credential File     : {s['credential_file']}")
    print(f"Authentication      : {s['authentication']}")
    print(f"Wallet API Client   : {s['wallet_api_client']}")
    print(f"Issuer ID           : {s['issuer_id']}")
    print(f"Generic Class ID    : {s['generic_class_id']}")
    print(f"Generic Class       : {s['generic_class']}")
    print(f"Final Result        : {s['final_result']}")
    print("="*60 + "\n")

if __name__ == "__main__":
    verify_setup()
