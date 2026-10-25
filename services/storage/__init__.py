from django.conf import settings
from .base import StorageService
from .local import LocalStorageService
from .r2 import CloudflareR2StorageService


def get_storage_service() -> StorageService:
    """
    Returns CloudflareR2StorageService if credentials and endpoint are configured;
    otherwise falls back to LocalStorageService for local dev / testing.
    """
    endpoint = getattr(settings, "R2_ENDPOINT_URL", "")
    key = getattr(settings, "R2_ACCESS_KEY_ID", "")
    secret = getattr(settings, "R2_SECRET_ACCESS_KEY", "")

    if endpoint and key and secret:
        return CloudflareR2StorageService()
    return LocalStorageService()


__all__ = ["StorageService", "LocalStorageService", "CloudflareR2StorageService", "get_storage_service"]
