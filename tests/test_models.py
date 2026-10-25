import uuid
import pytest
from django.contrib.auth import get_user_model
from apps.library.models import Document
from apps.assistant.models import Question, AnswerSource

User = get_user_model()


@pytest.mark.django_db
def test_user_creation_with_uuid():
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="securepassword123",
    )
    assert isinstance(user.id, uuid.UUID)
    assert user.email == "test@example.com"
    assert str(user) == "testuser"


@pytest.mark.django_db
def test_document_creation_and_ownership():
    user = User.objects.create_user(
        username="learner",
        email="learner@example.com",
        password="securepassword123",
    )
    doc = Document.objects.create(
        owner=user,
        title="Biology 101 Notes",
        subject="Biology",
        original_filename="biology_101.pdf",
        object_key=f"users/{user.id}/documents/bio101/original.pdf",
        status=Document.Status.QUEUED,
        size_bytes=1024,
    )
    assert isinstance(doc.id, uuid.UUID)
    assert doc.owner == user
    assert doc.status == Document.Status.QUEUED
    assert doc.title in str(doc)


@pytest.mark.django_db
def test_question_and_answer_source():
    user = User.objects.create_user(
        username="learner2",
        email="learner2@example.com",
        password="securepassword123",
    )
    doc = Document.objects.create(
        owner=user,
        title="Physics Notes",
        subject="Physics",
        original_filename="physics.pdf",
        object_key=f"users/{user.id}/documents/physics/original.pdf",
        status=Document.Status.READY,
    )
    q = Question.objects.create(
        owner=user,
        question="What is Newton's second law?",
        answer="F = ma",
        is_grounded=True,
    )
    source = AnswerSource.objects.create(
        question=q,
        document=doc,
        chunk_id=uuid.uuid4(),
        page_number=12,
        excerpt="Newton's second law states that F = ma.",
    )
    assert q.sources.count() == 1
    assert q.sources.first().document == doc
    assert q.sources.first().page_number == 12
