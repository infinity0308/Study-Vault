import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import BinaryIO
import logging
from django.conf import settings
from .base import StorageService

logger = logging.getLogger(__name__)


class CloudflareR2StorageService(StorageService):
    """Cloudflare R2 storage service using boto3 (S3-compatible)."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        bucket_name: str | None = None,
    ):
        self.endpoint_url = endpoint_url or getattr(settings, "R2_ENDPOINT_URL", "")
        self.access_key_id = access_key_id or getattr(settings, "R2_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or getattr(settings, "R2_SECRET_ACCESS_KEY", "")
        self.bucket_name = bucket_name or getattr(settings, "R2_BUCKET_NAME", "studyvault-docs")

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def upload_file(self, file_obj: BinaryIO, object_key: str, content_type: str = "application/pdf") -> str:
        try:
            file_obj.seek(0)
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_key,
                ExtraArgs={"ContentType": content_type},
            )
            return object_key
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code", "Unknown")
            if err_code == "NoSuchBucket":
                logger.critical("Cloudflare R2 Bucket '%s' does not exist. Create the bucket in your Cloudflare dashboard.", self.bucket_name)
            elif err_code in ("InvalidAccessKeyId", "SignatureDoesNotMatch"):
                logger.critical("Cloudflare R2 authentication failed: invalid R2_ACCESS_KEY_ID or R2_SECRET_ACCESS_KEY.")
            else:
                logger.error("Failed to upload file to R2 (%s): %s", err_code, e)
            raise

    def download_file(self, object_key: str) -> bytes:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=object_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error("Failed to download file from R2: %s", e)
            raise

    def delete_file(self, object_key: str) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            logger.error("Failed to delete file from R2: %s", e)
            return False

    def generate_presigned_url(self, object_key: str, expiration_seconds: int = 3600) -> str:
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expiration_seconds,
            )
            return url
        except ClientError as e:
            logger.error("Failed to generate presigned URL from R2: %s", e)
            raise
