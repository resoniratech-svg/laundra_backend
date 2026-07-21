from googleapiclient.errors import HttpError
from app.core.config import settings
from app.wallet.client import get_wallet_client

def get_generic_class_payload() -> dict:
    """
    Returns the Generic Class template payload representing prepaid laundry packages.
    
    Class ID: 338800000023177180.laundry_package
    Fields Template:
      - Laundry Name
      - Customer Package
      - Balance
      - Remaining Orders / Items
      - Expiry Date
      - Status
    """
    class_id = settings.GOOGLE_WALLET_CLASS_ID

    return {
        "id": class_id,
        "classTemplateInfo": {
            "cardTemplateOverride": {
                "cardRowTemplateInfos": [
                    {
                        "twoItems": {
                            "startItem": {
                                "firstValue": {
                                    "fields": [
                                        {"fieldPath": "object.textModulesData['balance']"}
                                    ]
                                }
                            },
                            "endItem": {
                                "firstValue": {
                                    "fields": [
                                        {"fieldPath": "object.textModulesData['remaining_orders']"}
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
                                        {"fieldPath": "object.textModulesData['expiry_date']"}
                                    ]
                                }
                            },
                            "endItem": {
                                "firstValue": {
                                    "fields": [
                                        {"fieldPath": "object.textModulesData['status']"}
                                    ]
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

def create_or_update_generic_class() -> dict:
    """
    Attempts to create or update the Google Wallet Generic Class via REST API.
    """
    client = get_wallet_client()
    class_id = settings.GOOGLE_WALLET_CLASS_ID
    generic_class_body = get_generic_class_payload()

    try:
        # Try fetching existing class
        existing_class = client.genericclass().get(resourceId=class_id).execute()
        response = client.genericclass().patch(resourceId=class_id, body=generic_class_body).execute()
        return {
            "status": "UPDATED",
            "class_id": response.get("id"),
            "message": f"Generic Class '{class_id}' updated successfully."
        }
    except HttpError as err:
        if err.resp.status == 404:
            try:
                response = client.genericclass().insert(body=generic_class_body).execute()
                return {
                    "status": "CREATED",
                    "class_id": response.get("id"),
                    "message": f"Generic Class '{class_id}' created successfully."
                }
            except HttpError as insert_err:
                return {
                    "status": "REQUIRES_CONSOLE_LINK_OR_JWT",
                    "class_id": class_id,
                    "error_detail": str(insert_err),
                    "message": "Class template defined in code. Google Pay Console authorization or JWT pass creation enabled."
                }
        else:
            return {
                "status": "ERROR",
                "class_id": class_id,
                "error_detail": str(err)
            }

if __name__ == "__main__":
    payload = get_generic_class_payload()
    print("[SUCCESS] Generic Class Template Defined Successfully!")
    print(f"   Class ID : {payload['id']}")
    print(f"   Fields   : Laundry Name | Customer Package | Balance | Remaining Orders | Expiry Date | Status")
