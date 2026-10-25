# Architecture

## Services

```text
Browser -> Nginx/TLS -> Django + DRF -> PostgreSQL
                           |  |  |
                           |  |  +-> Cloudflare R2 (private PDFs)
                           |  +----> Qdrant (vectors and chunk payload)
                           +-------> Redis task broker
                                      ^
                                      |
Django enqueues Celery tasks -> Celery worker -> PDF extraction/chunking
                                                |             |
                                                +-> embedding provider
Gemma answer provider <--------------------------+ (for answer generation)
```

The web, worker, PostgreSQL, Redis, and Qdrant services may run in Docker on an AWS VM for an MVP. R2 and the selected model API/runtime are external services.

## Responsibilities
- **Django/DRF:** authentication, permissions, upload validation, UI/API, retrieval orchestration, answer responses.
- **PostgreSQL:** source of truth for users, document records, statuses, and optional question history.
- **R2:** private original PDF objects; store object keys in the database, not permanent public URLs.
- **Qdrant:** vectors and minimal payload metadata; owner/document filters must be server-generated.
- **Celery/Redis:** asynchronous extraction, chunking, embedding, indexing, deletion, and retries.
- **Provider adapters:** isolate SDK-specific calls from application logic.

## Ingestion flow
1. Validate authenticated upload and create a `QUEUED` document row.
2. Store the PDF in a private R2 bucket using a random object key.
3. Enqueue a Celery task.
4. Worker extracts text page-by-page and checks for usable text.
5. Split text into overlapping chunks and attach page metadata.
6. Generate embeddings with the configured, verified embedding provider.
7. Upsert stable vector IDs and payload into Qdrant in batches.
8. Mark document `READY`; on failure mark `FAILED` with a safe message.
9. Reconciliation jobs handle tasks interrupted between systems.

R2, PostgreSQL, and Qdrant do not share a transaction. Make tasks idempotent and support reconciliation.

## Ask flow
1. Validate question and requested document scope.
2. Embed the question using the same embedding model/version used for indexed chunks.
3. Search Qdrant with a server-built owner filter.
4. Select relevant chunks, optionally applying a threshold calibrated by evaluation.
5. Send the question and limited retrieved context to Gemma.
6. Return answer, grounded/insufficient-context flag, and trusted source metadata.
7. UI renders answer and source cards.

## Suggested project structure
```text
studyvault/
├── manage.py
├── config/                 # settings, urls, ASGI/WSGI
├── apps/
│   ├── accounts/
│   ├── library/
│   ├── ingestion/
│   ├── assistant/
│   └── core/
├── services/
│   ├── storage/
│   ├── vector_store/
│   ├── embeddings/
│   └── llm/
├── templates/
├── static/css/
├── tests/
├── Dockerfile
├── compose.yaml
└── .env.example
```

Keep domain services separate from views. The web UI and REST API should call the same service layer. Avoid creating a generic `pages` app without a real domain responsibility.

## Resilience
Use timeouts, bounded retries with backoff, idempotent upserts, health checks, request IDs, and safe structured logs. Do not log API keys, signed URLs, or full private PDF text.
