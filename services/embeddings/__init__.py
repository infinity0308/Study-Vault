from django.conf import settings
from .base import EmbeddingProvider
from .google import GoogleGenAIEmbeddingProvider
from .mock import DeterministicEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    """
    Returns GoogleGenAIEmbeddingProvider if GEMMA_API_KEY is configured;
    otherwise falls back to DeterministicEmbeddingProvider for local testing/dev.
    """
    api_key = getattr(settings, "GEMMA_API_KEY", "")
    if api_key and api_key != "mock" and not api_key.startswith("test-"):
        return GoogleGenAIEmbeddingProvider()
    return DeterministicEmbeddingProvider(dimension=getattr(settings, "EMBEDDING_DIMENSION", 768))


__all__ = [
    "EmbeddingProvider",
    "GoogleGenAIEmbeddingProvider",
    "DeterministicEmbeddingProvider",
    "get_embedding_provider",
]
