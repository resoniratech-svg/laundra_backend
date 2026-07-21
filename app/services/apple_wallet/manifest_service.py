import hashlib
import json
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger("apple_wallet.manifest_service")

class ManifestService:
    """Generates Apple's manifest.json by hashing every file inside a pass bundle."""

    EXCLUDED_FILES = {
        "manifest.json",
        "signature",
        ".DS_Store",
    }

    def __init__(self, pass_directory: Path):
        self.pass_directory = pass_directory

    @staticmethod
    def sha1(file_path: Path) -> str:
        hash_object = hashlib.sha1()
        with open(file_path, "rb") as file:
            while chunk := file.read(8192):
                hash_object.update(chunk)
        return hash_object.hexdigest()

    def generate(self) -> Path:
        manifest = {}
        if self.pass_directory.exists():
            for file in sorted(self.pass_directory.iterdir()):
                if file.name in self.EXCLUDED_FILES:
                    continue
                if file.is_file():
                    manifest[file.name] = self.sha1(file)

        output = self.pass_directory / "manifest.json"
        self.pass_directory.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4, ensure_ascii=False)

        return output

    @classmethod
    def create_manifest_file(cls, pass_dir: Path) -> Path:
        service = cls(pass_dir)
        return service.generate()
