import sys
import json
from app.wallet.client import get_wallet_client

def main():
    client = get_wallet_client()
    test_ids = ["BCR2DN6D7LW37GQM", "338800000023177180"]
    
    for issuer_id in test_ids:
        class_id = f"{issuer_id}.laundry_package"
        print(f"\nTesting Issuer ID: {issuer_id} | Class ID: {class_id}")
        payload = {
            "id": class_id,
            "issuerName": "Laundra Laundry Services",
            "reviewStatus": "underReview"
        }
        try:
            res = client.genericclass().insert(body=payload).execute()
            print(f"SUCCESS! Generic Class Created with Issuer ID {issuer_id}:")
            print(json.dumps(res, indent=2))
        except Exception as e:
            print(f"Error for Issuer ID {issuer_id}: {e}")

if __name__ == "__main__":
    main()
