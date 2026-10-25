from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageService(ABC):
    """Abstract base class for object storage (e.g. Cloudflare R2)."""

    @abstractmethod
    def upload_file(self, file_obj: BinaryIO, object_key: str, content_type: str = "application/pdf") -> str:
        """Upload a file to object storage and return the object key."""
        pass

    @abstractmethod
    def download_file(self, object_key: str) -> bytes:
        """Download file content from object storage."""
        pass

    @abstractmethod
    def delete_file(self, object_key: str) -> bool:
        """Delete a file from object storage."""
        pass

    @abstractmethod
    def generate_presigned_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        """Generate a temporary presigned URL for private access."""
        pass
