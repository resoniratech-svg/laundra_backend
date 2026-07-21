from pathlib import Path
from typing import Optional
import uuid
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from PIL import Image
from app.core.config import settings


class QRService:
    """Service responsible for generating QR Code images."""

    def __init__(self, output_dir: Optional[Path] = None):
        out_base = output_dir or Path(settings.APPLE_WALLET_GENERATED_PATH)
        self.output_dir = out_base / "qr"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, data: str) -> Path:
        filename = f"{uuid.uuid4().hex}.png"
        file_path = self.output_dir / filename

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        image = qr.make_image(fill_color="black", back_color="white")
        image.save(file_path)
        return file_path

    @staticmethod
    def create_qr_image(message: str, box_size: int = 10, border: int = 4) -> Image.Image:
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(message)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    @classmethod
    def save_qr_code(cls, message: str, destination_path: Path):
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        img = cls.create_qr_image(message)
        img.save(destination_path)
