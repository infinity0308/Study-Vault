import uuid
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.library.models import Document, Collection

User = get_user_model()


@pytest.mark.django_db
def test_collections_crud_and_user_isolation():
    user_a = User.objects.create_user(username="student_a", email="a@example.com", password="password123")
    user_b = User.objects.create_user(username="student_b", email="b@example.com", password="password123")

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)

    # 1. Create Collection for User A
    res = client_a.post("/api/v1/collections/", {"name": "Physics — Semester 1", "description": "Mechanics and Waves"})
    assert res.status_code == 201
    col_a_id = res.json()["id"]

    # 2. Assign document to Collection
    doc = Document.objects.create(
        owner=user_a,
        collection_id=col_a_id,
        title="Physics Notes",
        original_filename="notes.pdf",
        object_key=f"users/{user_a.id}/notes.pdf",
        status=Document.Status.READY,
    )

    # 3. Retrieve Collection detail
    res_detail = client_a.get(f"/api/v1/collections/{col_a_id}/")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["name"] == "Physics — Semester 1"
    assert len(detail_data["documents"]) == 1
    assert detail_data["document_count"] == 1

    # 4. User B cannot see User A's collection
    client_b = APIClient()
    client_b.force_authenticate(user=user_b)
    res_b_list = client_b.get("/api/v1/collections/")
    assert res_b_list.status_code == 200
    assert len(res_b_list.json()) == 0

    res_b_detail = client_b.get(f"/api/v1/collections/{col_a_id}/")
    assert res_b_detail.status_code == 404

    # 5. Delete Collection: document is preserved with collection=None
    res_del = client_a.delete(f"/api/v1/collections/{col_a_id}/")
    assert res_del.status_code == 204
    doc.refresh_from_db()
    assert doc.collection is None


@pytest.mark.django_db
def test_public_landing_page():
    client = APIClient()
    # Unauthenticated root request serves public landing page
    res = client.get("/")
    assert res.status_code == 200
    assert b"Study from your own sources." in res.content
    assert b"Physics \xe2\x80\x94 Semester 1" in res.content
