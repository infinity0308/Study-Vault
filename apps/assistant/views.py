import time
import uuid
import logging
from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Question, AnswerSource
from .serializers import AskRequestSerializer, AskResponseSerializer
from apps.library.models import Document
from services.vector_store import get_vector_store_service
from services.embeddings import get_embedding_provider
from services.llm import get_answer_provider

logger = logging.getLogger(__name__)

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The uploaded study notes do not contain sufficient information to answer this question."
)


class AskAPIView(APIView):
    """
    RAG Question-Answering Endpoint.
    Scopes retrieval strictly to the authenticated user's READY documents.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AskRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        question_text = serializer.validated_data["question"].strip()
        requested_doc_ids = serializer.validated_data.get("document_ids", [])
        top_k = serializer.validated_data.get("top_k", 5)
        request_id = str(uuid.uuid4())

        # 1. Validate requested documents if provided
        if requested_doc_ids:
            owned_ready_docs = set(
                Document.objects.filter(
                    owner=request.user,
                    id__in=requested_doc_ids,
                    status=Document.Status.READY,
                ).values_list("id", flat=True)
            )
            # Ensure every requested ID belongs to user and is READY
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

        # 2. Embed the question
        try:
            embedding_provider = get_embedding_provider()
            q_vectors = embedding_provider.embed_texts([question_text])
            query_vector = q_vectors[0]
        except Exception as e:
            logger.error("Failed to embed question: %s", e)
            return Response(
                {"error": "Embedding service unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # 3. Search Qdrant vector store
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

        # 4. Handle insufficient context if no hits
        if not search_hits:
            return Response({
                "answer": INSUFFICIENT_CONTEXT_MESSAGE,
                "grounded": False,
                "insufficient_context": True,
                "sources": [],
                "request_id": request_id,
            })

        # 5. Build context & fetch document metadata
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
            title = doc_title_map.get(uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id, "Untitled Document")
            page = payload.get("page")
            text = payload.get("text", "")
            chunk_id = payload.get("chunk_id", hit["chunk_id"])

            context_parts.append(f"[Document: \"{title}\", Page {page}]\n{text}")
            sources.append({
                "document_id": doc_id,
                "document_title": title,
                "page": page,
                "chunk_id": chunk_id,
                "excerpt": text[:350] + ("..." if len(text) > 350 else ""),
            })

        combined_context = "\n\n".join(context_parts)

        # 6. Generate answer via Gemma provider
        try:
            answer_provider = get_answer_provider()
            raw_answer = answer_provider.generate_answer(
                question=question_text,
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

        # If abstained, don't return deceptive sources
        returned_sources = sources if is_grounded else []

        # 7. Record question history
        try:
            q_record = Question.objects.create(
                owner=request.user,
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

        return Response({
            "answer": raw_answer,
            "grounded": is_grounded,
            "insufficient_context": is_insufficient,
            "sources": returned_sources,
            "request_id": request_id,
        })


@login_required
def ask_view(request):
    ready_docs = Document.objects.filter(owner=request.user, status=Document.Status.READY)
    return render(request, "assistant/ask.html", {"ready_docs": ready_docs})
