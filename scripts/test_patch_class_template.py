import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.google_wallet import get_google_wallet_client, GoogleWalletClassService

def patch_live_class():
    client = get_google_wallet_client()
    class_id = GoogleWalletClassService.get_class_id()
    print(f"\n[Patch] Updating Live GenericClass: {class_id}")
    
    class_template_info = {
        "cardTemplateOverride": {
            "cardRowTemplateInfos": [
                {
                    "twoItems": {
                        "startItem": {
                            "firstValue": {
                                "fields": [
                                    {"fieldPath": "object.textModulesData['customer']"}
                                ]
                            }
                        },
                        "endItem": {
                            "firstValue": {
                                "fields": [
                                    {"fieldPath": "object.textModulesData['balance']"}
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
                                    {"fieldPath": "object.textModulesData['expiry']"}
                                ]
                            }
                        },
                        "endItem": {
                            "firstValue": {
                                "fields": [
                                    {"fieldPath": "object.textModulesData['services']"}
                                ]
                            }
                        }
                    }
                }
            ]
        }
    }

    body = {
        "id": class_id,
        "classTemplateInfo": class_template_info
    }

    try:
        patched_class = client.genericclass().patch(resourceId=class_id, body=body).execute()
        print("[Patch] SUCCESS! Live GenericClass Patched Payload:")
        print(json.dumps(patched_class, indent=2))
    except Exception as e:
        print(f"[Patch] Error patching class: {e}")

if __name__ == "__main__":
    patch_live_class()
