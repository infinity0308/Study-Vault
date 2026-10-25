import logging
from celery import shared_task
from django.utils import timezone
from apps.library.models import Document
from services.storage import get_storage_service
from services.vector_store import get_vector_store_service
from services.embeddings import get_embedding_provider
from services.pdf.extractor import PDFExtractor, PDFChunker, ScannedPDFError, PDFExtractionError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_document_task(self, document_id: str):
    """
    Asynchronous task to extract text from an uploaded PDF, chunk it,
    generate vector embeddings, and index them into Qdrant.
    """
    logger.info("Starting ingestion task for document: %s", document_id)

    try:
        doc = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.error("Document %s does not exist; aborting task.", document_id)
        return

    if doc.status == Document.Status.DELETING:
        logger.info("Document %s is marked for deletion; skipping ingestion.", document_id)
        return

    # Set processing status
    doc.status = Document.Status.PROCESSING
    doc.failure_code = ""
    doc.failure_message = ""
    doc.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])

    try:
        # 1. Download PDF from private storage (R2/Local)
        storage = get_storage_service()
        pdf_bytes = storage.download_file(doc.object_key)

        # 2. Extract text page-by-page
        pages = PDFExtractor.extract_pages(pdf_bytes)
        page_count = len(pages)

        # 3. Chunk text with page tracking
        chunker = PDFChunker()
        chunks = chunker.chunk_pages(pages, document_id=str(doc.id), owner_id=str(doc.owner_id))

        if not chunks:
            raise ScannedPDFError("No extractable chunks produced.")

        # 4. Generate embeddings
        embedding_provider = get_embedding_provider()
        texts = [c["text"] for c in chunks]
        embeddings = embedding_provider.embed_texts(texts)

        # 5. Index into Qdrant
        vector_store = get_vector_store_service()
        points = []
        for chunk, emb in zip(chunks, embeddings):
            points.append({
                "id": chunk["id"],
                "vector": emb,
                "payload": {
                    "owner_id": str(doc.owner_id),
                    "document_id": str(doc.id),
                    "chunk_id": chunk["id"],
                    "page": chunk["page"],
                    "text": chunk["text"],
                    "embedding_model": getattr(embedding_provider, "model_name", "default"),
                },
            })

        vector_store.upsert_points(points)

        # 6. Mark document READY
        doc.status = Document.Status.READY
        doc.page_count = page_count
        doc.chunk_count = len(chunks)
        doc.processed_at = timezone.now()
        doc.save(update_fields=["status", "page_count", "chunk_count", "processed_at", "updated_at"])

        logger.info("Successfully ingested document %s (%d pages, %d chunks)", document_id, page_count, len(chunks))
        return {"status": "SUCCESS", "document_id": document_id, "chunks": len(chunks)}

    except ScannedPDFError as e:
        logger.warning("Scanned PDF detected for document %s: %s", document_id, e)
        doc.status = Document.Status.FAILED
        doc.failure_code = "SCANNED_PDF"
        doc.failure_message = "Scanned PDFs without extractable text are not supported yet."
        doc.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])

    except PDFExtractionError as e:
        logger.warning("PDF extraction error for document %s: %s", document_id, e)
        doc.status = Document.Status.FAILED
        doc.failure_code = "EXTRACTION_FAILED"
        doc.failure_message = str(e)
        doc.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])

    except Exception as e:
        logger.exception("Unexpected error processing document %s: %s", document_id, e)
        # Bounded retries if retryable
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        doc.status = Document.Status.FAILED
        doc.failure_code = "PROCESSING_ERROR"
        doc.failure_message = "Document processing failed. Please retry."
        doc.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def delete_document_task(self, owner_id: str, document_id: str, object_key: str):
    """
    Asynchronous task to clean up Qdrant vector points,
    R2 storage object, and database record.
    """
    logger.info("Starting deletion cleanup for document %s (owner %s)", document_id, owner_id)

    # 1. Delete Qdrant vectors
    try:
        vector_store = get_vector_store_service()
        vector_store.delete_by_document(owner_id=owner_id, document_id=document_id)
    except Exception as e:
        logger.error("Failed to delete Qdrant points for document %s: %s", document_id, e)

    # 2. Delete file from R2 / storage
    try:
        storage = get_storage_service()
        storage.delete_file(object_key)
    except Exception as e:
        logger.error("Failed to delete file from storage for document %s: %s", document_id, e)

    # 3. Finalize database deletion
    try:
        Document.objects.filter(id=document_id, owner_id=owner_id).delete()
        logger.info("Completed deletion of document %s", document_id)
    except Exception as e:
        logger.error("Failed to remove Document record %s: %s", document_id, e)
