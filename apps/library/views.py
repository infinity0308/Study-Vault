import uuid
import logging
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from .models import Document, Collection
from .serializers import (
    DocumentSerializer,
    DocumentUpdateSerializer,
    DocumentUploadSerializer,
    CollectionSerializer,
)
from services.storage import get_storage_service
from services.pdf.extractor import PDFExtractor
from apps.ingestion.tasks import process_document_task, delete_document_task
from apps.assistant.models import Question

logger = logging.getLogger(__name__)


def trigger_ingestion_task(document_id: str):
    """Triggers celery task or executes directly if celery broker is offline."""
    try:
        process_document_task.delay(str(document_id))
    except Exception as e:
        logger.warning("Celery dispatch failed (%s); running synchronously.", e)
        process_document_task(str(document_id))


def trigger_deletion_task(owner_id: str, document_id: str, object_key: str):
    """Triggers celery deletion task or executes directly."""
    try:
        delete_document_task.delay(str(owner_id), str(document_id), object_key)
    except Exception as e:
        logger.warning("Celery deletion dispatch failed (%s); running synchronously.", e)
        delete_document_task(str(owner_id), str(document_id), object_key)


class StandardResultsPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50


# --- Collections REST API ---

class CollectionListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        collections = Collection.objects.filter(owner=request.user)
        serializer = CollectionSerializer(collections, many=True)
        return Response(serializer.data)

    def post(self, request):
        name = request.data.get("name", "").strip()
        if not name:
            return Response({"name": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        
        description = request.data.get("description", "").strip()
        col = Collection.objects.create(
            owner=request.user,
            name=name,
            description=description,
        )
        return Response(CollectionSerializer(col).data, status=status.HTTP_201_CREATED)


class CollectionDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_collection(self, request, pk):
        return get_object_or_404(Collection.objects.filter(owner=request.user), id=pk)

    def get(self, request, pk):
        col = self._get_collection(request, pk)
        data = CollectionSerializer(col).data
        docs = Document.objects.filter(owner=request.user, collection=col).exclude(status=Document.Status.DELETING)
        data["documents"] = DocumentSerializer(docs, many=True).data
        return Response(data)

    def patch(self, request, pk):
        col = self._get_collection(request, pk)
        name = request.data.get("name")
        description = request.data.get("description")
        if name is not None:
            col.name = name.strip() or col.name
        if description is not None:
            col.description = description.strip()
        col.save()
        return Response(CollectionSerializer(col).data)

    def delete(self, request, pk):
        col = self._get_collection(request, pk)
        # Disassociate documents rather than deleting them
        col.documents.update(collection=None)
        col.delete()
        return Response({"detail": "Collection deleted."}, status=status.HTTP_204_NO_CONTENT)


# --- Documents REST API ---

class DocumentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get(self, request):
        qs = Document.objects.filter(owner=request.user).exclude(status=Document.Status.DELETING)

        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(subject__icontains=search) | Q(original_filename__icontains=search))

        status_param = request.query_params.get("status", "").strip().upper()
        if status_param and status_param in Document.Status.values:
            qs = qs.filter(status=status_param)

        collection_param = request.query_params.get("collection", "").strip()
        if collection_param:
            qs = qs.filter(collection_id=collection_param)

        paginator = self.pagination_class()
        paginated_qs = paginator.paginate_queryset(qs, request)
        serializer = DocumentSerializer(paginated_qs, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file_obj = serializer.validated_data["file"]
        title = serializer.validated_data.get("title") or file_obj.name.rsplit(".", 1)[0]
        subject = serializer.validated_data.get("subject", "")
        description = serializer.validated_data.get("description", "")
        collection_id = serializer.validated_data.get("collection_id")

        collection = None
        if collection_id:
            collection = Collection.objects.filter(id=collection_id, owner=request.user).first()

        doc_id = uuid.uuid4()
        object_key = f"users/{request.user.id}/documents/{doc_id}/original.pdf"

        # 1. Upload to storage (R2 or Local fallback)
        try:
            storage = get_storage_service()
            storage.upload_file(file_obj, object_key, content_type="application/pdf")
        except Exception as e:
            logger.error("Failed to upload document file: %s", e)
            return Response(
                {"error": "Failed to store document file. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 2. Save Document record with QUEUED status
        doc = Document.objects.create(
            id=doc_id,
            owner=request.user,
            collection=collection,
            title=title,
            subject=subject,
            description=description,
            original_filename=file_obj.name,
            object_key=object_key,
            size_bytes=file_obj.size,
            status=Document.Status.QUEUED,
        )

        # 3. Enqueue background ingestion
        trigger_ingestion_task(str(doc.id))

        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_document(self, request, pk):
        return get_object_or_404(
            Document.objects.filter(owner=request.user).exclude(status=Document.Status.DELETING),
            id=pk,
        )

    def get(self, request, pk):
        doc = self._get_document(request, pk)
        data = DocumentSerializer(doc).data

        if request.query_params.get("download") == "1":
            try:
                storage = get_storage_service()
                data["download_url"] = storage.generate_presigned_url(doc.object_key)
            except Exception as e:
                logger.error("Failed to generate download URL: %s", e)
                data["download_url"] = None

        return Response(data)

    def patch(self, request, pk):
        doc = self._get_document(request, pk)
        serializer = DocumentUpdateSerializer(doc, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(DocumentSerializer(doc).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        doc = self._get_document(request, pk)
        doc.status = Document.Status.DELETING
        doc.save(update_fields=["status", "updated_at"])

        trigger_deletion_task(str(request.user.id), str(doc.id), doc.object_key)

        return Response(
            {"detail": "Document scheduled for deletion."},
            status=status.HTTP_202_ACCEPTED,
        )


class DocumentRetryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        doc = get_object_or_404(Document.objects.filter(owner=request.user), id=pk)

        if doc.status == Document.Status.PROCESSING:
            return Response(
                {"error": "Document is already being processed."},
                status=status.HTTP_409_CONFLICT,
            )

        doc.status = Document.Status.QUEUED
        doc.failure_code = ""
        doc.failure_message = ""
        doc.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])

        trigger_ingestion_task(str(doc.id))

        return Response(DocumentSerializer(doc).data, status=status.HTTP_200_OK)


# --- HTML Template Views ---

def home_view(request):
    """
    Renders Public Landing Page for unauthenticated users,
    or renders the Chat-First interface for authenticated users.
    """
    if not request.user.is_authenticated:
        return render(request, "library/landing.html")
    from apps.assistant.views import chat_view
    return chat_view(request)


@login_required
def overview_view(request):
    """
    Renders the Chat-First interface for authenticated users.
    """
    from apps.assistant.views import chat_view
    return chat_view(request)


@login_required
def library_view(request):
    user_docs = Document.objects.filter(owner=request.user).exclude(status=Document.Status.DELETING)
    collections = Collection.objects.filter(owner=request.user).order_by("name")
    subjects = sorted(list(set(d.subject for d in user_docs if d.subject)))

    return render(
        request,
        "library/library.html",
        {
            "collections": collections,
            "subjects": subjects,
        },
    )


@login_required
def collections_view(request):
    collections = Collection.objects.filter(owner=request.user).order_by("-updated_at")
    return render(request, "library/collections.html", {"collections": collections})


@login_required
def collection_detail_view(request, pk):
    col = get_object_or_404(Collection.objects.filter(owner=request.user), id=pk)
    docs = Document.objects.filter(owner=request.user, collection=col).exclude(status=Document.Status.DELETING)
    return render(request, "library/collection_detail.html", {"collection": col, "documents": docs})


@login_required
def document_preview_view(request, pk):
    doc = get_object_or_404(Document.objects.filter(owner=request.user).exclude(status=Document.Status.DELETING), id=pk)
    
    # Try extracting preview text if available
    preview_pages = []
    try:
        storage = get_storage_service()
        pdf_bytes = storage.download_file(doc.object_key)
        extracted = PDFExtractor.extract_pages(pdf_bytes)
        preview_pages = extracted[:10]  # First 10 pages for preview
    except Exception as e:
        logger.warning("Could not extract preview text for doc %s: %s", doc.id, e)

    return render(
        request,
        "library/document_preview.html",
        {
            "document": doc,
            "preview_pages": preview_pages,
        },
    )
