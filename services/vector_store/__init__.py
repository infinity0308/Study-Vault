from django.conf import settings
from .base import VectorStoreService
from .qdrant import QdrantVectorStore


def get_vector_store_service(in_memory: bool = False) -> VectorStoreService:
    """Return QdrantVectorStore instance."""
    if in_memory:
        return QdrantVectorStore(url=":memory:")
    return QdrantVectorStore()


__all__ = ["VectorStoreService", "QdrantVectorStore", "get_vector_store_service"]
