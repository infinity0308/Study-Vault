import uuid
from django.conf import settings
from django.db import models
from apps.library.models import Document


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question = models.TextField()
    answer = models.TextField(blank=True, default="")
    is_grounded = models.BooleanField(default=False)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    model_version = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Q by {self.owner}: {self.question[:50]}"


class AnswerSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="answer_sources",
    )
    chunk_id = models.UUIDField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    excerpt = models.TextField()

    def __str__(self):
        return f"Source for Q {self.question_id} from doc {self.document_id} p.{self.page_number}"
