import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.google_wallet import get_google_wallet_client, GoogleWalletClassService

def audit_live_class():
    client = get_google_wallet_client()
    class_id = GoogleWalletClassService.get_class_id()
    print(f"\n[Audit] Fetching Live GenericClass: {class_id}")
    
    try:
        live_class = client.genericclass().get(resourceId=class_id).execute()
        print("[Audit] SUCCESS! Live GenericClass Payload:")
        print(json.dumps(live_class, indent=2))
    except Exception as e:
        print(f"[Audit] Error fetching class: {e}")

if __name__ == "__main__":
    audit_live_class()
