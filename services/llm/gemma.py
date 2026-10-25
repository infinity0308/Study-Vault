import logging
from django.conf import settings
from google import genai
from google.genai import types
from .base import AnswerProvider
from .mock import GROUNDED_SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)


class GoogleGemmaAnswerProvider(AnswerProvider):
    """
    Google Gemma Answer Provider using the official google-genai SDK.
    Connects to Gemma models (e.g. gemma-2-9b-it, gemma-2-27b-it).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        self.api_key = api_key or getattr(settings, "GEMMA_API_KEY", "")
        self.model_name = model_name or getattr(settings, "GEMMA_MODEL", "gemma-2-9b-it")

        if not self.api_key:
            raise ValueError("Google API key is missing. Set GEMMA_API_KEY or GOOGLE_API_KEY.")

        self.client = genai.Client(api_key=self.api_key)

    def generate_answer(self, *, question: str, context: str) -> str:
        prompt = (
            f"{GROUNDED_SYSTEM_INSTRUCTION}\n\n"
            f"--- BEGIN STUDY EXCERPTS (UNTRUSTED DATA) ---\n"
            f"{context}\n"
            f"--- END STUDY EXCERPTS ---\n\n"
            f"User Question: {question}\n\n"
            f"Answer:"
        )

        try:
            config = types.GenerateContentConfig(
                temperature=0.2,  # Low temperature for strict factual grounding
                max_output_tokens=1024,
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                return response.text.strip()
            return "The uploaded study notes do not contain sufficient information to answer this question."
        except Exception as e:
            err_str = str(e)
            if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str or "403" in err_str:
                logger.critical("Google Gemma API Key is invalid or lacking permissions: %s", e)
            elif "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower() or "429" in err_str:
                logger.critical("Google Gemma API quota exceeded: %s", e)
            elif "NOT_FOUND" in err_str or "not found" in err_str.lower() or "404" in err_str:
                logger.critical("Gemma model '%s' not found. Verify GEMMA_MODEL in .env: %s", self.model_name, e)
            else:
                logger.error("Failed to generate answer from Gemma model %s: %s", self.model_name, e)
            raise
