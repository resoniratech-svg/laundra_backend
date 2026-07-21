from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import uuid
from typing import Optional

class PackageService:
    """Packages a Wallet pass directory into a .pkpass file."""

    REQUIRED_FILES = {
        "pass.json",
        "manifest.json",
        "signature",
    }

    def __init__(self, pass_directory: Path):
        self.pass_directory = pass_directory
        self.output_directory = pass_directory.parent / "pkpass"
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def validate(self):
        if not self.pass_directory.exists():
            raise FileNotFoundError(f"Pass directory does not exist: {self.pass_directory}")

        existing = {
            file.name
            for file in self.pass_directory.iterdir()
            if file.is_file()
        }

        missing = self.REQUIRED_FILES - existing
        if missing:
            raise FileNotFoundError(f"Missing required files: {sorted(missing)}")

    def package(self, custom_filename: Optional[str] = None) -> Path:
        self.validate()
        filename = custom_filename or f"{uuid.uuid4().hex}.pkpass"
        output_file = self.output_directory / filename

        with ZipFile(output_file, "w", ZIP_DEFLATED) as archive:
            for file in sorted(self.pass_directory.iterdir()):
                if file.is_file():
                    archive.write(file, arcname=file.name)

        return output_file

    def package_pkpass(self, staging_dir: Path, filename: str = "wallet.pkpass") -> Path:
        svc = PackageService(staging_dir)
        return svc.package(custom_filename=filename)
