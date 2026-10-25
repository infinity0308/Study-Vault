from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class VectorStoreService(ABC):
    """Abstract base class for vector storage (e.g. Qdrant)."""

    @abstractmethod
    def ensure_collection(self) -> None:
        """Create or verify the vector collection idempotently."""
        pass

    @abstractmethod
    def upsert_points(self, points: List[Dict[str, Any]]) -> None:
        """Upsert points with vectors and payloads."""
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        owner_id: str,
        document_ids: Optional[List[str]] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Search vector store filtered by owner and optional document IDs."""
        pass

    @abstractmethod
    def delete_by_document(self, owner_id: str, document_id: str) -> None:
        """Delete all points associated with a document."""
        pass
