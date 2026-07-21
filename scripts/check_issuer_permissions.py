import json
from app.wallet.client import get_wallet_client

def main():
    client = get_wallet_client()
    try:
        # Try generic class list or permissions test
        print("Checking service account permissions...")
        res = client.permissions().list().execute()
        print("Permissions response:", json.dumps(res, indent=2))
    except Exception as e:
        print("Permissions API Error:", e)

if __name__ == "__main__":
    main()
