from abc import ABC, abstractmethod


class AnswerProvider(ABC):
    """Abstract base class for LLM answer generation providers."""

    @abstractmethod
    def generate_answer(self, *, question: str, context: str) -> str:
        """Generate an answer grounded in supplied excerpts."""
        pass
