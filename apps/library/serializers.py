import re
import uuid
from rest_framework import serializers
from django.conf import settings
from .models import Document, Collection


class CollectionSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ("id", "name", "description", "document_count", "created_at", "updated_at")
        read_only_fields = ("id", "document_count", "created_at", "updated_at")

    def get_document_count(self, obj):
        return obj.documents.exclude(status=Document.Status.DELETING).count()


class DocumentSerializer(serializers.ModelSerializer):
    collection_id = serializers.UUIDField(source="collection.id", read_only=True, allow_null=True)
    collection_name = serializers.CharField(source="collection.name", read_only=True, allow_null=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "subject",
            "description",
            "collection_id",
            "collection_name",
            "original_filename",
            "size_bytes",
            "page_count",
            "chunk_count",
            "status",
            "failure_code",
            "failure_message",
            "created_at",
            "updated_at",
            "processed_at",
        )
        read_only_fields = (
            "id",
            "collection_id",
            "collection_name",
            "original_filename",
            "size_bytes",
            "page_count",
            "chunk_count",
            "status",
            "failure_code",
            "failure_message",
            "created_at",
            "updated_at",
            "processed_at",
        )


class DocumentUpdateSerializer(serializers.ModelSerializer):
    collection_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Document
        fields = ("title", "subject", "description", "collection_id")

    def update(self, instance, validated_data):
        if "collection_id" in validated_data:
            col_id = validated_data.pop("collection_id")
            if col_id:
                col = Collection.objects.filter(id=col_id, owner=instance.owner).first()
                instance.collection = col
            else:
                instance.collection = None
        return super().update(instance, validated_data)


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    title = serializers.CharField(max_length=255, required=False)
    subject = serializers.CharField(max_length=100, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    collection_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_file(self, value):
        max_size = getattr(settings, "MAX_UPLOAD_SIZE_BYTES", 25 * 1024 * 1024)
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size exceeds maximum limit of {max_size // (1024 * 1024)}MB."
            )

        name = value.name.lower()
        if not name.endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are supported.")

        header = value.read(1024)
        value.seek(0)
        if b"%PDF-" not in header:
            raise serializers.ValidationError("Invalid file signature. File is not a valid PDF document.")

        return value

    def validate_title(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Title cannot be blank.")
        return cleaned
