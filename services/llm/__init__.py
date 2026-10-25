from django.conf import settings
from .base import AnswerProvider
from .gemma import GoogleGemmaAnswerProvider
from .mock import MockGemmaAnswerProvider


def get_answer_provider() -> AnswerProvider:
    """
    Returns GoogleGemmaAnswerProvider if GEMMA_API_KEY is configured;
    otherwise falls back to MockGemmaAnswerProvider for local dev / testing.
    """
    api_key = getattr(settings, "GEMMA_API_KEY", "")
    if api_key and api_key != "mock" and not api_key.startswith("test-"):
        return GoogleGemmaAnswerProvider()
    return MockGemmaAnswerProvider()


__all__ = [
    "AnswerProvider",
    "GoogleGemmaAnswerProvider",
    "MockGemmaAnswerProvider",
    "get_answer_provider",
]
