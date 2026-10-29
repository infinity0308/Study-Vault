import time
import uuid
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.db import models
from django.db.models import Q, Count
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Conversation, Question, AnswerSource
from .serializers import (
    AskRequestSerializer,
    AskResponseSerializer,
    ConversationListSerializer,
    ConversationDetailSerializer,
)
from apps.library.models import Document, Collection
from services.vector_store import get_vector_store_service
from services.embeddings import get_embedding_provider
from services.llm import get_answer_provider

logger = logging.getLogger(__name__)

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The uploaded study notes do not contain sufficient information to answer this question."
)


def _generate_title(text: str) -> str:
    """Generate a clean, concise conversation title from user's initial question."""
    clean = " ".join(text.split())
    if not clean:
        return "Study Session"
    if len(clean) <= 45:
        return clean[:1].upper() + clean[1:]
    truncated = clean[:45]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return (truncated[:1].upper() + truncated[1:]).strip() + "..."


class ConversationListCreateAPIView(APIView):
    """
    List user's saved conversations or create a new conversation thread.
    Supports ?search= to find conversations by title or question content.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Conversation.objects.filter(owner=request.user)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(questions__question__icontains=search)
                | Q(questions__answer__icontains=search)
            ).distinct()

        qs = qs.annotate(question_count=Count("questions")).order_by("-updated_at")
        serializer = ConversationListSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        title = request.data.get("title", "").strip() or "New Study Session"
        collection_id = request.data.get("collection_id")
        document_ids = request.data.get("document_ids", [])

        collection = None
        if collection_id:
            collection = get_object_or_404(
                Collection.objects.filter(owner=request.user), id=collection_id
            )

        conv = Conversation.objects.create(
            owner=request.user,
            title=title,
            collection=collection,
        )

        if document_ids:
            valid_docs = Document.objects.filter(
                owner=request.user,
                id__in=document_ids,
                status=Document.Status.READY,
            )
            conv.documents.set(valid_docs)

        return Response(
            ConversationDetailSerializer(conv).data,
            status=status.HTTP_201_CREATED,
        )


class ConversationDetailAPIView(APIView):
    """
    Retrieve, rename, or delete an existing conversation.
    """
    permission_classes = [IsAuthenticated]

    def _get_conversation(self, request, pk):
        return get_object_or_404(Conversation.objects.filter(owner=request.user), id=pk)

    def get(self, request, pk):
        conv = self._get_conversation(request, pk)
        return Response(ConversationDetailSerializer(conv).data)

    def patch(self, request, pk):
        conv = self._get_conversation(request, pk)
        title = request.data.get("title")
        if title is not None:
            conv.title = title.strip() or conv.title

        if "collection_id" in request.data:
            cid = request.data.get("collection_id")
            if cid:
                col = get_object_or_404(Collection.objects.filter(owner=request.user), id=cid)
                conv.collection = col
            else:
                conv.collection = None

        conv.save(update_fields=["title", "collection", "updated_at"])
        return Response(ConversationDetailSerializer(conv).data)

    def delete(self, request, pk):
        conv = self._get_conversation(request, pk)
        conv.delete()
        return Response({"detail": "Conversation deleted."}, status=status.HTTP_204_NO_CONTENT)


class AskAPIView(APIView):
    """
    RAG Question-Answering Endpoint.
    Scopes retrieval strictly to the authenticated user's READY documents.
    Preserves and links to conversation threads with conversational memory.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AskRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        question_text = serializer.validated_data["question"].strip()
        requested_doc_ids = serializer.validated_data.get("document_ids", [])
        collection_id = serializer.validated_data.get("collection_id")
        conversation_id = serializer.validated_data.get("conversation_id")
        top_k = serializer.validated_data.get("top_k", 5)
        request_id = str(uuid.uuid4())

        # 1. Resolve conversation if specified
        conv = None
        if conversation_id:
            conv = get_object_or_404(
                Conversation.objects.filter(owner=request.user), id=conversation_id
            )
            # Inherit scope if not explicitly overridden
            if not requested_doc_ids and not collection_id:
                if conv.collection_id:
                    collection_id = conv.collection_id
                elif conv.documents.exists():
                    requested_doc_ids = list(conv.documents.values_list("id", flat=True))

        # 2. Resolve collection scope if provided
        if collection_id and not requested_doc_ids:
            col = get_object_or_404(
                Collection.objects.filter(owner=request.user), id=collection_id
            )
            requested_doc_ids = list(
                Document.objects.filter(
                    owner=request.user,
                    collection=col,
                    status=Document.Status.READY,
                ).values_list("id", flat=True)
            )

        # 3. Validate requested documents
        if requested_doc_ids:
            owned_ready_docs = set(
                Document.objects.filter(
                    owner=request.user,
                    id__in=requested_doc_ids,
                    status=Document.Status.READY,
                ).values_list("id", flat=True)
            )
            for doc_id in requested_doc_ids:
                if doc_id not in owned_ready_docs:
                    return Response(
                        {"error": f"Document {doc_id} is invalid, not owned by you, or not ready."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            filter_doc_ids = [str(d) for d in requested_doc_ids]
        else:
            filter_doc_ids = None

        start_time = time.time()

        # 4. Formulate retrieval query (context-aware for follow-up questions)
        retrieval_query = question_text
        if conv:
            last_turn = conv.questions.order_by("-created_at").first()
            if last_turn:
                words = set(question_text.lower().split())
                referential_cues = {"it", "this", "that", "they", "these", "those", "why", "how", "more", "explain", "second", "first", "third", "which", "does"}
                if len(words) < 8 or words & referential_cues:
                    retrieval_query = f"{last_turn.question} {question_text}"

        # Embed the retrieval query
        try:
            embedding_provider = get_embedding_provider()
            q_vectors = embedding_provider.embed_texts([retrieval_query])
            query_vector = q_vectors[0]
        except Exception as e:
            logger.error("Failed to embed question: %s", e)
            return Response(
                {"error": "Embedding service unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 5. Search Qdrant vector store
        try:
            vector_store = get_vector_store_service()
            score_thresh = getattr(settings, "RAG_SCORE_THRESHOLD", None)
            search_hits = vector_store.search(
                query_vector=query_vector,
                owner_id=str(request.user.id),
                document_ids=filter_doc_ids,
                top_k=top_k,
                score_threshold=score_thresh,
            )
        except Exception as e:
            logger.error("Failed to query vector database: %s", e)
            return Response(
                {"error": "Vector database unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Ensure conversation exists
        if conv is None:
            conv = Conversation.objects.create(
                owner=request.user,
                title=_generate_title(question_text),
                collection_id=collection_id,
            )
            if requested_doc_ids:
                conv.documents.set(requested_doc_ids)

        # 6. Handle insufficient context if no hits
        if not search_hits:
            elapsed_ms = int((time.time() - start_time) * 1000)
            q_record = Question.objects.create(
                owner=request.user,
                conversation=conv,
                question=question_text,
                answer=INSUFFICIENT_CONTEXT_MESSAGE,
                is_grounded=False,
                latency_ms=elapsed_ms,
                model_version="system",
            )
            conv.updated_at = timezone.now()
            conv.save(update_fields=["updated_at"])

            return Response({
                "answer": INSUFFICIENT_CONTEXT_MESSAGE,
                "grounded": False,
                "insufficient_context": True,
                "sources": [],
                "request_id": request_id,
                "conversation_id": str(conv.id),
                "conversation_title": conv.title,
                "question_id": str(q_record.id),
            })

        # 7. Build context & fetch document metadata
        hit_doc_ids = set()
        for hit in search_hits:
            doc_id_val = hit["payload"].get("document_id")
            if doc_id_val:
                hit_doc_ids.add(doc_id_val)

        doc_title_map = dict(
            Document.objects.filter(id__in=hit_doc_ids).values_list("id", "title")
        )

        context_parts = []
        sources = []

        for hit in search_hits:
            payload = hit["payload"]
            doc_id = payload.get("document_id")
            title = doc_title_map.get(
                uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id,
                "Untitled Document",
            )
            page = payload.get("page")
            text = payload.get("text", "")
            chunk_id = payload.get("chunk_id", hit["chunk_id"])

            context_parts.append(f"[Document: \"{title}\", Page {page}]\n{text}")
            sources.append({
                "document_id": str(doc_id),
                "document_title": title,
                "page": page,
                "chunk_id": str(chunk_id),
                "excerpt": text[:350] + ("..." if len(text) > 350 else ""),
            })

        combined_context = "\n\n".join(context_parts)

        # 8. Conversational memory (including prior questions, answers, and former chunk evidence)
        recent_turns = conv.questions.prefetch_related("sources__document").order_by("-created_at")[:3]
        if recent_turns:
            history_blocks = []
            for pt in reversed(recent_turns):
                ans_sample = pt.answer[:250] + ("..." if len(pt.answer) > 250 else "")
                turn_block = f"Student: {pt.question}\nAssistant: {ans_sample}"
                pt_sources = list(pt.sources.all()[:2])
                if pt_sources:
                    cites = [
                        f'"{s.excerpt[:130]}..." (from {s.document.title if s.document else "notes"}, p. {s.page_number or "N/A"})'
                        for s in pt_sources
                    ]
                    turn_block += f"\n[Former evidence cited in this conversation: {'; '.join(cites)}]"
                history_blocks.append(turn_block)
            history_prefix = "Recent conversation thread for context:\n" + "\n\n".join(history_blocks) + "\n\n"
            full_question = f"{history_prefix}Student's new question: {question_text}"
        else:
            full_question = question_text

        # 9. Generate answer via Gemma provider
        try:
            answer_provider = get_answer_provider()
            raw_answer = answer_provider.generate_answer(
                question=full_question,
                context=combined_context,
            )
        except Exception as e:
            logger.error("Answer generation failed: %s", e)
            return Response(
                {"error": "Answer generation service unavailable. Please retry."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Check if model abstained
        is_insufficient = (
            INSUFFICIENT_CONTEXT_MESSAGE.lower() in raw_answer.lower()
            or "do not provide enough information" in raw_answer.lower()
            or "does not contain sufficient information" in raw_answer.lower()
        )
        is_grounded = not is_insufficient
        returned_sources = sources if is_grounded else []

        # 10. Update conversation & record question turn
        try:
            if conv.title in ("New Study Session", "New conversation", ""):
                conv.title = _generate_title(question_text)
            conv.updated_at = timezone.now()
            conv.save()

            q_record = Question.objects.create(
                owner=request.user,
                conversation=conv,
                question=question_text,
                answer=raw_answer,
                is_grounded=is_grounded,
                latency_ms=elapsed_ms,
                model_version=getattr(answer_provider, "model_name", "gemma-2-9b-it"),
            )
            if is_grounded:
                for s in sources:
                    try:
                        doc_obj = Document.objects.filter(id=s["document_id"]).first()
                        if doc_obj:
                            AnswerSource.objects.create(
                                question=q_record,
                                document=doc_obj,
                                chunk_id=s["chunk_id"],
                                page_number=s["page"],
                                excerpt=s["excerpt"],
                            )
                    except Exception as ex:
                        logger.warning("Failed to save answer source: %s", ex)
        except Exception as e:
            logger.warning("Failed to persist question record: %s", e)
            q_record = None

        return Response({
            "answer": raw_answer,
            "grounded": is_grounded,
            "insufficient_context": is_insufficient,
            "sources": returned_sources,
            "request_id": request_id,
            "conversation_id": str(conv.id),
            "conversation_title": conv.title,
            "question_id": str(q_record.id) if q_record else None,
        })


def _group_conversations(conversations):
    """Group conversations by: Today, Yesterday, Previous 7 days, Older."""
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    groups = {
        "today": [],
        "yesterday": [],
        "previous_7_days": [],
        "older": [],
    }

    for c in conversations:
        c_date = c.updated_at.date()
        if c_date == today:
            groups["today"].append(c)
        elif c_date == yesterday:
            groups["yesterday"].append(c)
        elif c_date >= week_ago:
            groups["previous_7_days"].append(c)
        else:
            groups["older"].append(c)

    return groups


@login_required
def chat_view(request, conversation_id=None):
    """
    Renders the chat-first study interface.
    Passes library metrics, ready documents, collections, and conversation history.
    """
    user = request.user
    user_docs = Document.objects.filter(owner=user).exclude(status=Document.Status.DELETING)
    ready_docs = user_docs.filter(status=Document.Status.READY).order_by("title")
    processing_docs_count = user_docs.filter(
        status__in=[Document.Status.QUEUED, Document.Status.PROCESSING]
    ).count()

    collections = Collection.objects.filter(owner=user).order_by("name")

    conversations = (
        Conversation.objects.filter(owner=user)
        .annotate(question_count=Count("questions"))
        .order_by("-updated_at")
    )
    grouped_conversations = _group_conversations(conversations)

    active_conversation = None
    if conversation_id:
        active_conversation = get_object_or_404(
            Conversation.objects.filter(owner=user), id=conversation_id
        )

    # Optional query params: ?doc=UUID or ?collection=UUID
    selected_doc_id = request.GET.get("doc", "")
    selected_collection_id = request.GET.get("collection", "")

    context = {
        "user": user,
        "ready_docs": ready_docs,
        "collections": collections,
        "total_docs_count": user_docs.count(),
        "ready_docs_count": ready_docs.count(),
        "processing_docs_count": processing_docs_count,
        "total_collections_count": collections.count(),
        "conversations": conversations,
        "grouped_conversations": grouped_conversations,
        "active_conversation": active_conversation,
        "selected_doc_id": selected_doc_id,
        "selected_collection_id": selected_collection_id,
    }

    return render(request, "assistant/ask.html", context)


@login_required
def ask_view(request):
    """Redirects legacy /ask/ route to the chat view."""
    return chat_view(request)
