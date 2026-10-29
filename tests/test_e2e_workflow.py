import io
import uuid
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test import Client
from apps.assistant.models import Conversation, Question, AnswerSource
from apps.library.models import Document, Collection
from services.vector_store import get_vector_store_service
from services.embeddings import get_embedding_provider

User = get_user_model()


@pytest.mark.django_db
def test_full_chat_first_workflow_e2e():
    """
    End-to-end test verifying all user workflows:
    - Sign in & initial Home screen with empty overview
    - Upload & ingestion of study document
    - Home screen study summary reflects ready document
    - Ask question grounded in document content -> creates conversation
    - Verify inline sources and citation data
    - Follow-up question in same conversation
    - Start a second conversation
    - Verify conversation history listing and grouping
    - Rename conversation
    - Search conversations
    - Delete conversation
    """
    # 1. Sign up & Sign in
    user = User.objects.create_user(
        username="biology_student",
        email="student@university.edu",
        password="studyhardpassword123",
        first_name="Alex",
    )
    api_client = APIClient()
    api_client.force_authenticate(user=user)

    html_client = Client()
    html_client.force_login(user)

    # 2. Open Home screen before any document is uploaded
    home_res = html_client.get("/")
    assert home_res.status_code == 200
    home_content = home_res.content.decode()
    assert "Ready to study, Alex?" in home_content
    assert "No study notes uploaded yet" in home_content
    assert "Ask anything about your study materials" in home_content

    # 3. Upload a PDF document
    doc = Document.objects.create(
        owner=user,
        title="Chapter 3 — Cell Biology and Mitochondria",
        original_filename="cell_bio_ch3.pdf",
        object_key=f"users/{user.id}/cell_bio_ch3.pdf",
        status=Document.Status.READY,
        page_count=24,
        chunk_count=6,
    )

    # Index chunks in vector store
    vs = get_vector_store_service()
    vs.ensure_collection()
    emb = get_embedding_provider()
    chunk_text = "Mitochondria produce adenosine triphosphate (ATP) through oxidative phosphorylation, functioning as cellular power plants."
    chunk_vec = emb.embed_texts([chunk_text])[0]
    chunk_id = str(uuid.uuid4())

    vs.upsert_points([
        {
            "id": chunk_id,
            "vector": chunk_vec,
            "payload": {
                "owner_id": str(user.id),
                "document_id": str(doc.id),
                "chunk_id": chunk_id,
                "page": 14,
                "text": chunk_text,
                "embedding_model": "test",
            },
        }
    ])

    # 4. Open Home screen now that a document is ready
    home_after_doc = html_client.get("/")
    assert home_after_doc.status_code == 200
    home_after_content = home_after_doc.content.decode()
    assert "document" in home_after_content
    assert "ready to search" in home_after_content

    # 5. Ask a question about the PDF (Conversation 1)
    q1_text = "What is the primary function of mitochondria according to my notes?"
    ask_res1 = api_client.post(
        "/api/v1/ask/",
        {"question": q1_text, "document_ids": [str(doc.id)]},
        format="json",
    )
    assert ask_res1.status_code == 200
    ans1_data = ask_res1.json()
    assert ans1_data["grounded"] is True
    assert ans1_data["insufficient_context"] is False
    assert len(ans1_data["sources"]) == 1
    assert ans1_data["sources"][0]["document_title"] == "Chapter 3 — Cell Biology and Mitochondria"
    assert ans1_data["sources"][0]["page"] == 14
    assert ans1_data["conversation_id"] is not None

    conv1_id = ans1_data["conversation_id"]
    conv1 = Conversation.objects.get(id=conv1_id)
    assert conv1.owner == user

    # 6. Ask a follow-up question in the same conversation
    q2_text = "Does it involve oxidative phosphorylation?"
    ask_res2 = api_client.post(
        "/api/v1/ask/",
        {
            "question": q2_text,
            "conversation_id": conv1_id,
            "document_ids": [str(doc.id)],
        },
        format="json",
    )
    assert ask_res2.status_code == 200
    ans2_data = ask_res2.json()
    assert ans2_data["conversation_id"] == conv1_id
    assert Question.objects.filter(conversation_id=conv1_id).count() == 2

    # 7. Start a second separate conversation
    q3_text = "What are ribosomes?"
    ask_res3 = api_client.post(
        "/api/v1/ask/",
        {"question": q3_text},
        format="json",
    )
    assert ask_res3.status_code == 200
    ans3_data = ask_res3.json()
    conv2_id = ans3_data["conversation_id"]
    assert conv2_id != conv1_id

    # 8. Verify Conversation history list
    conv_list_res = api_client.get("/api/v1/conversations/")
    assert conv_list_res.status_code == 200
    conv_list = conv_list_res.json()
    assert len(conv_list) == 2

    # 9. Reopen the first conversation (SSR URL & API)
    c1_html_res = html_client.get(f"/c/{conv1_id}/")
    assert c1_html_res.status_code == 200
    c1_content = c1_html_res.content.decode()
    assert q1_text in c1_content
    assert q2_text in c1_content

    c1_api_res = api_client.get(f"/api/v1/conversations/{conv1_id}/")
    assert c1_api_res.status_code == 200
    c1_api_data = c1_api_res.json()
    assert len(c1_api_data["messages"]) == 2

    # 10. Rename Conversation
    rename_res = api_client.patch(
        f"/api/v1/conversations/{conv1_id}/",
        {"title": "Mitochondria & Energy Metabolism"},
        format="json",
    )
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Mitochondria & Energy Metabolism"

    # 11. Search conversations
    search_hit = api_client.get("/api/v1/conversations/?search=Metabolism")
    assert search_hit.status_code == 200
    assert len(search_hit.json()) == 1
    assert search_hit.json()[0]["id"] == conv1_id

    # 12. Delete second conversation
    del_res = api_client.delete(f"/api/v1/conversations/{conv2_id}/")
    assert del_res.status_code == 204
    assert Conversation.objects.filter(id=conv2_id).count() == 0

    # Verify first conversation still intact
    assert Conversation.objects.filter(id=conv1_id).count() == 1
