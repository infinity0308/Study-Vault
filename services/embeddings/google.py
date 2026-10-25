import logging
from typing import List
from django.conf import settings
from google import genai
from google.genai import types
from .base import EmbeddingProvider

logger = logging.getLogger(__name__)


class GoogleGenAIEmbeddingProvider(EmbeddingProvider):
    """
    Google GenAI Embedding Provider using the official google-genai SDK.
    Uses models such as 'gemini-embedding-001'.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        dimension: int = 768,
    ):
        self.api_key = api_key or (getattr(settings, "GEMMA_API_KEY", "") if settings.configured else "")
        raw_model = model_name or (getattr(settings, "EMBEDDING_MODEL", "gemini-embedding-001") if settings.configured else "gemini-embedding-001")
        if raw_model in ("text-embedding-004", "models/text-embedding-004", ""):
            self.model_name = "gemini-embedding-001"
        else:
            self.model_name = raw_model
        self.dimension = dimension or (getattr(settings, "EMBEDDING_DIMENSION", 768) if settings.configured else 768)

        if not self.api_key:
            raise ValueError("Google API key is missing. Set GEMMA_API_KEY or GOOGLE_API_KEY.")

        self.client = genai.Client(api_key=self.api_key)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        embeddings: List[List[float]] = []
        batch_size = 50  # Keep batch size within API limits

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                config = types.EmbedContentConfig(output_dimensionality=self.dimension)
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=batch,
                    config=config,
                )
                if hasattr(response, "embeddings") and response.embeddings:
                    for emb in response.embeddings:
                        vec = list(emb.values)
                        if len(vec) != self.dimension:
                            logger.warning(
                                "Embedding dimension mismatch: expected %d, got %d",
                                self.dimension,
                                len(vec),
                            )
                        embeddings.append(vec)
                elif hasattr(response, "embedding") and response.embedding:
                    embeddings.append(list(response.embedding.values))
                else:
                    raise ValueError("No embeddings returned by Google GenAI.")
            except Exception as e:
                err_str = str(e)
                if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str or "403" in err_str:
                    logger.critical("Google GenAI API Key is invalid: %s", e)
                elif "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower() or "429" in err_str:
                    logger.critical("Google GenAI Embedding quota exceeded: %s", e)
                elif "NOT_FOUND" in err_str or "404" in err_str:
                    logger.critical("Embedding model '%s' not found. Verify EMBEDDING_MODEL in .env: %s", self.model_name, e)
                else:
                    logger.error("Failed to generate Google GenAI embeddings: %s", e)
                raise

        return embeddings
