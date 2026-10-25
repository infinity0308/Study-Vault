import pytest
from services.vector_store.qdrant import reset_in_memory_qdrant


@pytest.fixture(autouse=True)
def configure_test_settings(settings):
    """Automatically configure isolated in-memory vector store and eager tasks for tests."""
    settings.QDRANT_URL = ":memory:"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.GEMMA_API_KEY = ""
    reset_in_memory_qdrant()
    yield
    reset_in_memory_qdrant()
