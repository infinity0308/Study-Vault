import uuid
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from apps.assistant.models import Conversation, Question
from apps.library.models import Document, Collection

User = get_user_model()


@pytest.mark.django_db
def test_home_view_unauthenticated():
    client = Client()
    res = client.get("/")
    assert res.status_code == 200
    assert "Study from your own sources" in res.content.decode()


@pytest.mark.django_db
def test_home_view_authenticated():
    user = User.objects.create_user(username="viewer", email="viewer@example.com", password="password123")
    client = Client()
    client.force_login(user)

    res = client.get("/")
    assert res.status_code == 200
    content = res.content.decode()
    assert "Ready to study" in content
    assert "Ask anything about your study materials" in content


@pytest.mark.django_db
def test_conversation_detail_view_authenticated():
    user = User.objects.create_user(username="convuser", email="conv@example.com", password="password123")
    client = Client()
    client.force_login(user)

    conv = Conversation.objects.create(owner=user, title="Organic Chemistry Reactions")
    Question.objects.create(
        owner=user,
        conversation=conv,
        question="What is an SN2 reaction?",
        answer="An SN2 reaction is a type of nucleophilic substitution...",
        is_grounded=True,
    )

    res = client.get(f"/c/{conv.id}/")
    assert res.status_code == 200
    content = res.content.decode()
    assert "Organic Chemistry Reactions" in content
    assert "What is an SN2 reaction?" in content


@pytest.mark.django_db
def test_library_and_settings_views_authenticated():
    user = User.objects.create_user(username="libuser", email="lib@example.com", password="password123")
    client = Client()
    client.force_login(user)

    # Library
    res_lib = client.get("/library/")
    assert res_lib.status_code == 200
    assert "All Documents" in res_lib.content.decode()

    # Collections
    res_col = client.get("/library/collections/")
    assert res_col.status_code == 200
    assert "Study Collections" in res_col.content.decode()

    # Settings
    res_set = client.get("/accounts/settings/")
    assert res_set.status_code == 200
    assert "Settings & Account" in res_set.content.decode()
