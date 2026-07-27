import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger("apple_wallet.template_service")

class TemplateService:
    """Service to load and render base pass.json templates."""

    def __init__(self, template_path: Optional[Path] = None):
        self.template_path = template_path or Path(settings.APPLE_WALLET_TEMPLATE_PATH)

    def load_template(self) -> Dict[str, Any]:
        candidates = [
            self.template_path / "pass.json" if self.template_path.is_dir() else self.template_path,
            Path("templates/apple_wallet/pass/pass.json"),
            Path("templates/apple_wallet/pass.json")
        ]
        for p in candidates:
            if p and p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("generic") and data["generic"].get("primaryFields"):
                            return data
                        elif not hasattr(self, "_fallback_template"):
                            self._fallback_template = data
                except Exception as e:
                    logger.error(f"Failed to load template at {p}: {e}")

        if hasattr(self, "_fallback_template"):
            return self._fallback_template

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

    def fill_placeholders(self, data: Any, context: Dict[str, Any]) -> Any:
        """Recursively replaces {{placeholder}} in strings with values from context dict."""
        if isinstance(data, str):
            def replacer(match):
                key = match.group(1).strip()
                val = context.get(key)
                return str(val) if val is not None else match.group(0)
            return re.sub(r"\{\{\s*(\w+)\s*\}\}", replacer, data)
        elif isinstance(data, dict):
            return {k: self.fill_placeholders(v, context) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.fill_placeholders(item, context) for item in data]
        return data

    def render_pass_json(self, target_file: Path, pass_data: Dict[str, Any]) -> Path:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(pass_data, f, indent=2, ensure_ascii=False)
        return target_file
