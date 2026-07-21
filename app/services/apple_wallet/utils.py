import hashlib
import logging
import shutil
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Tuple, Union
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12

logger = logging.getLogger("apple_wallet.utils")

def calculate_sha1(data_or_file: Union[Path, bytes]) -> str:
    """Calculates SHA-1 hash for a file path or byte sequence."""
    hasher = hashlib.sha1()
    if isinstance(data_or_file, Path):
        with open(data_or_file, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
    else:
        hasher.update(data_or_file)
    return hasher.hexdigest()

def parse_pkcs12_certificate(
    p12_path: Path, password: Optional[str] = None
) -> Tuple[Optional[rsa.RSAPrivateKey], Optional[x509.Certificate], list]:
    """Parses PKCS12 (.p12) bundle and extracts private key and certificates."""
    if not p12_path.exists():
        return None, None, []

    try:
        p12_data = p12_path.read_bytes()
        pwd_bytes = password.encode("utf-8") if password else None
        key, cert, add_certs = pkcs12.load_key_and_certificates(p12_data, pwd_bytes)
        return key, cert, add_certs or []
    except Exception as e:
        logger.error(f"Failed to parse P12 certificate at {p12_path}: {e}")
        return None, None, []

def parse_x509_certificate(cert_path: Path) -> Optional[x509.Certificate]:
    """Parses x509 certificate supporting both DER (.cer) and PEM (.pem) formats."""
    if not cert_path.exists():
        return None

    try:
        data = cert_path.read_bytes()
        try:
            return x509.load_der_x509_certificate(data)
        except Exception:
            return x509.load_pem_x509_certificate(data)
    except Exception as e:
        logger.error(f"Failed to parse x509 certificate at {cert_path}: {e}")
        return None

@contextmanager
def temporary_directory(base_path: Path, prefix: str = "pass_") -> Generator[Path, None, None]:
    """Creates a clean staging directory cleaned up on context exit."""
    temp_dir = base_path / f"temp_{prefix}"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        yield temp_dir
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def copy_file(src: Union[str, Path], dest: Union[str, Path]) -> Path:
    """Copies file safely creating parent folders if needed."""
    src_path = Path(src)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_path, dest_path)
    return dest_path

def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensures a directory exists."""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def create_pkpass_archive(source_dir: Path, output_file: Path) -> Path:
    """Zips directory contents into a .pkpass ZIP archive."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)
    return output_file
