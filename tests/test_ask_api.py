import uuid
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.library.models import Document
from apps.assistant.models import Question
from services.vector_store import get_vector_store_service
from services.embeddings import get_embedding_provider

User = get_user_model()


@pytest.mark.django_db
def test_ask_api_validation():
    user = User.objects.create_user(username="asker", email="asker@example.com", password="password123")
    client = APIClient()

    # 1. Unauthenticated -> 403
    res_unauth = client.post("/api/v1/ask/", {"question": "What is ATP?"})
    assert res_unauth.status_code == 403

    client.force_authenticate(user=user)

    # 2. Blank question -> 400
    res_blank = client.post("/api/v1/ask/", {"question": ""})
    assert res_blank.status_code == 400

    # 3. Invalid document ID -> 400
    fake_doc_id = str(uuid.uuid4())
    res_fake = client.post("/api/v1/ask/", {"question": "What is ATP?", "document_ids": [fake_doc_id]})
    assert res_fake.status_code == 400


@pytest.mark.django_db
def test_ask_api_grounded_answer_and_abstention(monkeypatch):
    user = User.objects.create_user(username="asker2", email="asker2@example.com", password="password123")
    client = APIClient()
    client.force_authenticate(user=user)

    doc = Document.objects.create(
        owner=user,
        title="Cellular Biology",
        original_filename="cell.pdf",
        object_key=f"users/{user.id}/cell.pdf",
        status=Document.Status.READY,
        page_count=5,
        chunk_count=2,
    )

    # Index sample chunk in Qdrant
    vs = get_vector_store_service()
    vs.ensure_collection()
    emb = get_embedding_provider()
    text = "Mitochondria generate most of the chemical energy needed to power the cell biochemical reactions."
    vec = emb.embed_texts([text])[0]
    chunk_id = str(uuid.uuid4())

    vs.upsert_points([
        {
            "id": chunk_id,
            "vector": vec,
            "payload": {
                "owner_id": str(user.id),
                "document_id": str(doc.id),
                "chunk_id": chunk_id,
                "page": 3,
                "text": text,
                "embedding_model": "test",
            },
        }
    ])

    # 1. Answerable question -> grounded response with source citation
    res = client.post(
        "/api/v1/ask/",
        {
            "question": "What is the function of mitochondria?",
            "document_ids": [str(doc.id)],
        },
        format="json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data["grounded"] is True
    assert data["insufficient_context"] is False
    assert len(data["sources"]) == 1
    assert data["sources"][0]["document_title"] == "Cellular Biology"
    assert data["sources"][0]["page"] == 3
    assert "chemical energy" in data["answer"] or "mitochondria" in data["answer"].lower()

    # Verify database question record was saved
    assert Question.objects.filter(owner=user).count() == 1
    saved_q = Question.objects.first()
    assert saved_q.is_grounded is True
    assert saved_q.sources.count() == 1

    # 2. Unanswerable question -> abstention
    res_unans = client.post(
        "/api/v1/ask/",
        {
            "question": "What is the capital city of France?",
            "document_ids": [str(doc.id)],
        },
        format="json",
    )
    assert res_unans.status_code == 200
    data_unans = res_unans.json()
    assert data_unans["insufficient_context"] is True
    assert data_unans["grounded"] is False
    assert "not contain sufficient information" in data_unans["answer"]
    assert len(data_unans["sources"]) == 0


@pytest.mark.django_db
def test_ask_api_multi_turn_conversation():
    user = User.objects.create_user(username="multiturn", email="multi@example.com", password="password123")
    client = APIClient()
    client.force_authenticate(user=user)

    doc = Document.objects.create(
        owner=user,
        title="Genetics Notes",
        original_filename="genetics.pdf",
        object_key=f"users/{user.id}/genetics.pdf",
        status=Document.Status.READY,
        page_count=10,
        chunk_count=3,
    )

    vs = get_vector_store_service()
    vs.ensure_collection()
    emb = get_embedding_provider()
    text = "DNA is composed of two strands forming a double helix carrying genetic instructions."
    vec = emb.embed_texts([text])[0]
    chunk_id = str(uuid.uuid4())

    vs.upsert_points([
        {
            "id": chunk_id,
            "vector": vec,
            "payload": {
                "owner_id": str(user.id),
                "document_id": str(doc.id),
                "chunk_id": chunk_id,
                "page": 1,
                "text": text,
                "embedding_model": "test",
            },
        }
    ])

    # Turn 1: No conversation_id -> creates new conversation
    res1 = client.post(
        "/api/v1/ask/",
        {"question": "What is DNA composed of?", "document_ids": [str(doc.id)]},
        format="json",
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["conversation_id"] is not None
    assert d1["conversation_title"] != ""
    conv_id = d1["conversation_id"]

    # Turn 2: Follow-up using same conversation_id
    res2 = client.post(
        "/api/v1/ask/",
        {
            "question": "Does it form a double helix?",
            "conversation_id": conv_id,
            "document_ids": [str(doc.id)],
        },
        format="json",
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["conversation_id"] == conv_id

    # Verify conversation now has 2 questions
    assert Question.objects.filter(conversation_id=conv_id).count() == 2
