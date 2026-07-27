import logging
import shutil
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw

from app.core.config import settings

logger = logging.getLogger("apple_wallet.image_service")

class ImageService:
    """Service to handle, resize, and copy Apple Wallet pass image assets."""

    REQUIRED_ASSETS = [
        "icon.png", "icon@2x.png", "icon@3x.png",
        "logo.png", "logo@2x.png", "logo@3x.png",
        "thumbnail.png", "thumbnail@2x.png",
        "strip.png", "strip@2x.png",
        "background.png"
    ]

    def __init__(self, assets_dir: Optional[Path] = None):
        self.assets_dir = assets_dir or Path(settings.APPLE_WALLET_ASSETS_PATH)

    def prepare_pass_images(self, target_dir: Path):
        """Copies available image assets to target pass directory, creating defaults if missing."""
        for filename in self.REQUIRED_ASSETS:
            src = self.assets_dir / filename
            dest = target_dir / filename
            if src.exists():
                shutil.copy(src, dest)
            elif filename in ["icon.png", "icon@2x.png", "logo.png", "logo@2x.png"]:
                self.create_placeholder_image(dest, filename)

    def create_placeholder_image(self, dest_path: Path, filename: str):
        """Generates fallback placeholder PNG image."""
        w, h = (58, 58) if "icon" in filename else (160, 50)
        img = Image.new("RGBA", (w, h), (15, 23, 42, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([1, 1, w - 2, h - 2], outline=(255, 255, 255, 200), width=2)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest_path)
