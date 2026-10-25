import re
import hashlib
import math
from typing import List
from .base import EmbeddingProvider


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic pseudo-semantic embedding provider for testing and development
    when an external API key is not configured.
    Combines word-level hash representations so texts sharing terms
    have measurable cosine similarity.
    """

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def _hash_token(self, token: str) -> List[float]:
        vec = []
        seed = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(self.dimension):
            idx1 = (i * 3) % len(seed)
            idx2 = (i * 7 + 1) % len(seed)
            val = (seed[idx1] - 128) / 128.0 + (seed[idx2] - 128) / 256.0
            vec.append(val)
        return vec

    def _embed_single(self, text: str) -> List[float]:
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            tokens = ["empty"]

        combined = [0.0] * self.dimension
        for token in tokens:
            t_vec = self._hash_token(token)
            for i in range(self.dimension):
                combined[i] += t_vec[i]

        # L2-normalize
        norm = math.sqrt(sum(x * x for x in combined)) or 1.0
        return [x / norm for x in combined]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_single(t) for t in texts]
