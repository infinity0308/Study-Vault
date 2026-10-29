import uuid
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.assistant.models import Conversation, Question, AnswerSource
from apps.library.models import Document, Collection

User = get_user_model()


@pytest.mark.django_db
def test_conversation_crud_and_search():
    user = User.objects.create_user(username="chatuser", email="chat@example.com", password="password123")
    other_user = User.objects.create_user(username="other", email="other@example.com", password="password123")
    client = APIClient()

    # 1. Unauthenticated -> 403
    res_unauth = client.get("/api/v1/conversations/")
    assert res_unauth.status_code == 403

    client.force_authenticate(user=user)

    # 2. Initially empty
    res = client.get("/api/v1/conversations/")
    assert res.status_code == 200
    assert len(res.json()) == 0

    # 3. Create conversation
    col = Collection.objects.create(owner=user, name="Physics 101")
    res_create = client.post(
        "/api/v1/conversations/",
        {"title": "Kinematics Questions", "collection_id": str(col.id)},
        format="json",
    )
    assert res_create.status_code == 201
    conv_data = res_create.json()
    conv_id = conv_data["id"]
    assert conv_data["title"] == "Kinematics Questions"
    assert conv_data["collection_name"] == "Physics 101"

    # Add a question to this conversation
    conv_obj = Conversation.objects.get(id=conv_id)
    Question.objects.create(
        owner=user,
        conversation=conv_obj,
        question="What is acceleration?",
        answer="Acceleration is the rate of change of velocity.",
        is_grounded=True,
    )

    # 4. Retrieve conversation detail
    res_detail = client.get(f"/api/v1/conversations/{conv_id}/")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["id"] == conv_id
    assert len(detail_data["messages"]) == 1
    assert detail_data["messages"][0]["question"] == "What is acceleration?"

    # 5. Search conversations
    res_search = client.get("/api/v1/conversations/?search=acceleration")
    assert res_search.status_code == 200
    assert len(res_search.json()) == 1

    res_search_empty = client.get("/api/v1/conversations/?search=mitochondria")
    assert res_search_empty.status_code == 200
    assert len(res_search_empty.json()) == 0

    # 6. Rename conversation
    res_patch = client.patch(
        f"/api/v1/conversations/{conv_id}/",
        {"title": "Updated Kinematics"},
        format="json",
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "Updated Kinematics"

    # 7. Other user cannot access or delete
    client_other = APIClient()
    client_other.force_authenticate(user=other_user)
    res_other = client_other.get(f"/api/v1/conversations/{conv_id}/")
    assert res_other.status_code == 404

    # 8. Delete conversation
    res_delete = client.delete(f"/api/v1/conversations/{conv_id}/")
    assert res_delete.status_code == 204
    assert Conversation.objects.filter(id=conv_id).count() == 0
    assert Question.objects.filter(conversation_id=conv_id).count() == 0
