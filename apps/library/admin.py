from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "page_count", "chunk_count", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "subject", "original_filename")
