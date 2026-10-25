import uuid
from django.conf import settings
from django.db import models


class Collection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "-updated_at"]),
        ]

    def __str__(self):
        return self.name


class Document(models.Model):
    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"
        DELETING = "DELETING", "Deleting"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    collection = models.ForeignKey(
        Collection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    
    original_filename = models.CharField(max_length=255)
    object_key = models.CharField(max_length=512, unique=True)
    content_type = models.CharField(max_length=100, default="application/pdf")
    size_bytes = models.BigIntegerField(default=0)
    
    page_count = models.PositiveIntegerField(null=True, blank=True)
    chunk_count = models.PositiveIntegerField(null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    failure_code = models.CharField(max_length=50, blank=True, default="")
    failure_message = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"
