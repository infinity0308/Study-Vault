import io
import uuid
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.library.models import Document

User = get_user_model()


def create_minimal_pdf_bytes(text: str = "Cell biology lecture notes content.") -> bytes:
    """Creates a valid minimal PDF byte sequence with searchable text."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.django_db
def test_document_user_isolation():
    user_a = User.objects.create_user(username="usera", email="a@example.com", password="password123")
    user_b = User.objects.create_user(username="userb", email="b@example.com", password="password123")

    doc_a = Document.objects.create(
        owner=user_a,
        title="User A Notes",
        original_filename="a.pdf",
        object_key=f"users/{user_a.id}/a.pdf",
        status=Document.Status.READY,
    )

    doc_b = Document.objects.create(
        owner=user_b,
        title="User B Notes",
        original_filename="b.pdf",
        object_key=f"users/{user_b.id}/b.pdf",
        status=Document.Status.READY,
    )

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)

    # User A lists documents: should only see doc_a
    res = client_a.get("/api/v1/documents/")
    assert res.status_code == 200
    results = res.json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == str(doc_a.id)

    # User A attempts to view doc_b: must be 404
    res_b = client_a.get(f"/api/v1/documents/{doc_b.id}/")
    assert res_b.status_code == 404

    # User A attempts to delete doc_b: must be 404
    res_del = client_a.delete(f"/api/v1/documents/{doc_b.id}/")
    assert res_del.status_code == 404


@pytest.mark.django_db
def test_document_upload_validation():
    user = User.objects.create_user(username="uploader", email="up@example.com", password="password123")
    client = APIClient()
    client.force_authenticate(user=user)

    # 1. Reject non-PDF file
    text_file = SimpleUploadedFile("notes.txt", b"Hello text file", content_type="text/plain")
    res1 = client.post("/api/v1/documents/", {"file": text_file, "title": "Text Notes"}, format="multipart")
    assert res1.status_code == 400

    # 2. Reject fake PDF without %PDF- magic bytes
    fake_pdf = SimpleUploadedFile("notes.pdf", b"Not a real pdf header", content_type="application/pdf")
    res2 = client.post("/api/v1/documents/", {"file": fake_pdf, "title": "Fake PDF"}, format="multipart")
    assert res2.status_code == 400

    # 3. Accept valid PDF
    real_pdf_bytes = create_minimal_pdf_bytes("Valid study notes on genetics.")
    valid_pdf = SimpleUploadedFile("genetics.pdf", real_pdf_bytes, content_type="application/pdf")
    res3 = client.post("/api/v1/documents/", {"file": valid_pdf, "title": "Genetics Notes"}, format="multipart")
    assert res3.status_code == 201
    data = res3.json()
    assert data["title"] == "Genetics Notes"
    # Status should transition to READY after ingestion
    assert data["status"] in (Document.Status.QUEUED, Document.Status.READY)


@pytest.mark.django_db
def test_document_retry_conflict():
    user = User.objects.create_user(username="retryuser", email="r@example.com", password="password123")
    client = APIClient()
    client.force_authenticate(user=user)

    doc = Document.objects.create(
        owner=user,
        title="Processing Doc",
        original_filename="p.pdf",
        object_key=f"users/{user.id}/p.pdf",
        status=Document.Status.PROCESSING,
    )

    # Retrying a currently processing document must return 409 Conflict
    res = client.post(f"/api/v1/documents/{doc.id}/retry/")
    assert res.status_code == 409
