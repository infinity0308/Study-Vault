import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from .base import VectorStoreService

logger = logging.getLogger(__name__)

_SHARED_IN_MEMORY_CLIENT: Optional[QdrantClient] = None


def reset_in_memory_qdrant():
    """Helper to reset shared in-memory Qdrant client between tests."""
    global _SHARED_IN_MEMORY_CLIENT
    _SHARED_IN_MEMORY_CLIENT = None


class QdrantVectorStore(VectorStoreService):
    """
    Qdrant vector database service.
    Implements collection creation, payload indexing, batch upserts,
    scoped search, and document cleanup.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        dimension: int | None = None,
        client: QdrantClient | None = None,
    ):
        global _SHARED_IN_MEMORY_CLIENT
        self.url = url or getattr(settings, "QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or getattr(settings, "QDRANT_API_KEY", "") or None
        self.collection_name = collection_name or getattr(settings, "QDRANT_COLLECTION_NAME", "study_chunks_v1")
        self.dimension = dimension or getattr(settings, "EMBEDDING_DIMENSION", 768)

        if client is not None:
            self.client = client
        elif self.url == ":memory:":
            if _SHARED_IN_MEMORY_CLIENT is None:
                _SHARED_IN_MEMORY_CLIENT = QdrantClient(":memory:")
            self.client = _SHARED_IN_MEMORY_CLIENT
        else:
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=5.0,
                check_compatibility=False,
            )

    def ensure_collection(self) -> None:
        """Idempotently ensure collection exists with proper vector dimension and payload indexes."""
        try:
            collections = [col.name for col in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest_models.VectorParams(
                        size=self.dimension,
                        distance=rest_models.Distance.COSINE,
                    ),
                )
                logger.info("Created Qdrant collection %s with dimension %s", self.collection_name, self.dimension)

                # Remote servers require payload indexes; local in-memory doesn't
                if self.url != ":memory:":
                    try:
                        self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="owner_id",
                            field_schema=rest_models.PayloadSchemaType.KEYWORD,
                        )
                        self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name="document_id",
                            field_schema=rest_models.PayloadSchemaType.KEYWORD,
                        )
                        logger.info("Created payload indexes for owner_id and document_id")
                    except Exception as idx_err:
                        logger.warning("Could not create payload index: %s", idx_err)
        except Exception as e:
            logger.error("Failed to ensure Qdrant collection %s: %s", self.collection_name, e)
            raise

    def upsert_points(self, points: List[Dict[str, Any]]) -> None:
        """
        Upsert a list of chunk points into Qdrant.
        Each point dict must have: id, vector, payload.
        """
        if not points:
            return

        self.ensure_collection()

        qdrant_points = []
        for pt in points:
            vec = pt["vector"]
            if len(vec) != self.dimension:
                raise ValueError(
                    f"Vector dimension mismatch: expected {self.dimension}, got {len(vec)}"
                )
            qdrant_points.append(
                rest_models.PointStruct(
                    id=str(pt["id"]),
                    vector=vec,
                    payload=pt["payload"],
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=qdrant_points,
            wait=True,
        )
        logger.info("Upserted %d points into %s", len(qdrant_points), self.collection_name)

    def search(
        self,
        query_vector: List[float],
        owner_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search strictly scoped to the owner,
        optionally filtered by specific document IDs.
        """
        if len(query_vector) != self.dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {self.dimension}, got {len(query_vector)}"
            )

        self.ensure_collection()

        must_conditions = [
            rest_models.FieldCondition(
                key="owner_id",
                match=rest_models.MatchValue(value=str(owner_id)),
            )
        ]

        if document_ids:
            must_conditions.append(
                rest_models.FieldCondition(
                    key="document_id",
                    match=rest_models.MatchAny(any=[str(d) for d in document_ids]),
                )
            )

        qdrant_filter = rest_models.Filter(must=must_conditions)

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        ).points

        formatted = []
        for hit in results:
            formatted.append({
                "chunk_id": str(hit.id),
                "score": float(hit.score),
                "payload": hit.payload or {},
            })
        return formatted

    def delete_by_document(self, owner_id: str, document_id: str) -> None:
        """Delete all points matching owner_id and document_id."""
        self.ensure_collection()
        del_filter = rest_models.Filter(
            must=[
                rest_models.FieldCondition(
                    key="owner_id",
                    match=rest_models.MatchValue(value=str(owner_id)),
                ),
                rest_models.FieldCondition(
                    key="document_id",
                    match=rest_models.MatchValue(value=str(document_id)),
                ),
            ]
        )
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=del_filter,
            wait=True,
        )
        logger.info("Deleted vectors for document %s (owner %s)", document_id, owner_id)
