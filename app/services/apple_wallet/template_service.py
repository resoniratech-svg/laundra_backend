import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger("apple_wallet.template_service")

class TemplateService:
    """Service to load and render base pass.json templates."""

    def __init__(self, template_path: Optional[Path] = None):
        self.template_path = template_path or Path(settings.APPLE_WALLET_TEMPLATE_PATH)

    def load_template(self) -> Dict[str, Any]:
        if self.template_path.exists():
            try:
                with open(self.template_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load template at {self.template_path}: {e}")

        return {
            "formatVersion": 1,
            "passTypeIdentifier": settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER,
            "serialNumber": "GENERIC-0001",
            "teamIdentifier": settings.APPLE_WALLET_TEAM_IDENTIFIER,
            "organizationName": settings.APP_NAME,
            "description": "Apple Wallet Pass",
            "logoText": settings.APP_NAME,
            "foregroundColor": "rgb(255, 255, 255)",
            "backgroundColor": "rgb(15, 23, 42)",
            "labelColor": "rgb(148, 163, 184)"
        }

    def render_pass_json(self, target_file: Path, pass_data: Dict[str, Any]) -> Path:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(pass_data, f, indent=2, ensure_ascii=False)
        return target_file
