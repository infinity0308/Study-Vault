import os
from pathlib import Path
from typing import BinaryIO
from django.conf import settings
from .base import StorageService


class LocalStorageService(StorageService):
    """Local filesystem storage used for local dev / testing or when R2 is unconfigured."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path(settings.MEDIA_ROOT) / "documents"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, object_key: str) -> Path:
        return self.base_dir / object_key

    def upload_file(self, file_obj: BinaryIO, object_key: str, content_type: str = "application/pdf") -> str:
        file_path = self._get_path(object_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_obj.seek(0)
        with open(file_path, "wb") as f:
            f.write(file_obj.read())
        return object_key

    def download_file(self, object_key: str) -> bytes:
        file_path = self._get_path(object_key)
        if not file_path.exists():
            raise FileNotFoundError(f"Object {object_key} not found at {file_path}")
        with open(file_path, "rb") as f:
            return f.read()

    def delete_file(self, object_key: str) -> bool:
        file_path = self._get_path(object_key)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def generate_presigned_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        # In local storage, return a local media path URL
        return f"{settings.MEDIA_URL}documents/{object_key}"
