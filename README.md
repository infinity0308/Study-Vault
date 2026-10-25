# StudyVault — Gemma-powered RAG learning assistant

StudyVault is a responsive learning website where users upload PDF notes, then ask questions answered from those notes using retrieval-augmented generation (RAG).

## Stack
- Python, Django, Django REST Framework
- Google Gemma for answer generation, through a verified supported endpoint/runtime
- Qdrant vector database
- Cloudflare R2 for private original PDFs
- PostgreSQL for application records
- Celery + Redis for background ingestion
- Docker Compose on AWS
- Django templates + responsive CSS; optional HTMX

## Documentation
- [Project description](PROJECT_DESCRIPTION.md)
- [Architecture](ARCHITECTURE.md)
- [REST API](API_SPEC.md)
- [Data model](DATA_MODEL.md)
- [UI/UX](UI_UX.md)
- [Ingestion and RAG](INGESTION_AND_RAG.md)
- [Security](SECURITY.md)
- [Deployment](DEPLOYMENT.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Gemma/API setup](API_AND_MODEL_SETUP.md)
- [Testing](TESTING.md)
- [Decisions and open questions](DECISIONS.md)

This is the documentation/specification pack, not the application code itself. Build the application in phases using these files as requirements.

## Important model note
Do not assume one Gemma API supports both text generation and embeddings. Verify the exact model/runtime and documented operations first. If embeddings are not supported, use a compatible documented embedding model/runtime and keep Gemma for answer generation rather than faking embeddings.
