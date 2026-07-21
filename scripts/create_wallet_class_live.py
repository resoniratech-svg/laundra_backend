import sys
import json
import logging

from app.core.config import settings
from app.wallet.client import get_wallet_client
from app.wallet.class_service import get_class_payload

logging.basicConfig(level=logging.INFO)

def main():
    client = get_wallet_client()
    class_id = settings.GOOGLE_WALLET_CLASS_ID
    payload = get_class_payload()
    
    print(f"Attempting to insert Google Wallet Generic Class: {class_id}")
    print(f"Payload:\n{json.dumps(payload, indent=2)}")

    try:
        res = client.genericclass().insert(body=payload).execute()
        print("\nSUCCESS! Generic Class Created via API:")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"\nAPI Result/Error: {e}")
        try:
            get_res = client.genericclass().get(resourceId=class_id).execute()
            print("\nGeneric Class Already Exists in Console:")
            print(json.dumps(get_res, indent=2))
        except Exception as get_e:
            print(f"Could not GET class either: {get_e}")

if __name__ == "__main__":
    main()
