import uuid
from rest_framework import serializers
from .models import Conversation, Question, AnswerSource
from apps.library.models import Document, Collection


class SourceSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    document_title = serializers.CharField()
    page = serializers.IntegerField(allow_null=True)
    chunk_id = serializers.UUIDField()
    excerpt = serializers.CharField()


class AskRequestSerializer(serializers.Serializer):
    question = serializers.CharField(min_length=1, max_length=1000, required=True)
    document_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    collection_id = serializers.UUIDField(required=False, allow_null=True)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    top_k = serializers.IntegerField(min_value=1, max_value=10, required=False, default=5)


class AskResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    grounded = serializers.BooleanField()
    insufficient_context = serializers.BooleanField()
    sources = SourceSerializer(many=True)
    request_id = serializers.CharField()
    conversation_id = serializers.UUIDField(required=False)
    conversation_title = serializers.CharField(required=False)
    question_id = serializers.UUIDField(required=False)


class QuestionDetailSerializer(serializers.ModelSerializer):
    sources = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            "id",
            "question",
            "answer",
            "is_grounded",
            "latency_ms",
            "model_version",
            "created_at",
            "sources",
        ]

    def get_sources(self, obj):
        return [
            {
                "document_id": str(s.document_id),
                "document_title": s.document.title if s.document else "Untitled Document",
                "page": s.page_number,
                "chunk_id": str(s.chunk_id),
                "excerpt": s.excerpt,
            }
            for s in obj.sources.select_related("document").all()
        ]


class ConversationListSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True)
    last_question = serializers.CharField(read_only=True)
    collection_name = serializers.CharField(source="collection.name", read_only=True, default=None)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "collection",
            "collection_name",
            "question_count",
            "last_question",
            "created_at",
            "updated_at",
        ]


class ConversationDetailSerializer(serializers.ModelSerializer):
    collection_name = serializers.CharField(source="collection.name", read_only=True, default=None)
    document_count = serializers.IntegerField(source="documents.count", read_only=True)
    documents = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "collection",
            "collection_name",
            "document_count",
            "documents",
            "created_at",
            "updated_at",
            "messages",
        ]

    def get_documents(self, obj):
        return [
            {"id": str(d.id), "title": d.title}
            for d in obj.documents.all()
        ]

    def get_messages(self, obj):
        questions = obj.questions.all().prefetch_related("sources__document").order_by("created_at")
        results = []
        for q in questions:
            src_list = [
                {
                    "document_id": str(s.document_id),
                    "document_title": s.document.title if s.document else "Untitled Document",
                    "page": s.page_number,
                    "chunk_id": str(s.chunk_id),
                    "excerpt": s.excerpt,
                }
                for s in q.sources.all()
            ]
            results.append({
                "id": str(q.id),
                "question": q.question,
                "answer": q.answer,
                "is_grounded": q.is_grounded,
                "latency_ms": q.latency_ms,
                "created_at": q.created_at.isoformat(),
                "sources": src_list,
            })
        return results
