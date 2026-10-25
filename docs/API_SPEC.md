# REST API Specification

Base path: `/api/v1/`. Use DRF serializers, ownership permissions, pagination, throttling, and consistent JSON errors. Session auth is a simple choice for a same-origin website; unsafe requests require CSRF protection.

## Authentication
- `POST /auth/login/`
- `POST /auth/logout/`
- `GET /auth/me/`
- Optional `GET /auth/csrf/` depending on the chosen frontend/auth setup.

Use one consistent Django auth system for HTML pages and API requests.

## Documents
- `GET /documents/` — list only current user's documents; support `search`, `status`, `page`, `page_size`.
- `POST /documents/` — multipart PDF upload (`file`, `title`, optional `subject`, `description`); return `201` with `QUEUED` status.
- `GET /documents/{id}/` — retrieve an owned document.
- `PATCH /documents/{id}/` — update user-editable metadata only.
- `DELETE /documents/{id}/` — immediately block access and begin asynchronous cleanup; `202 Accepted` is appropriate.
- `POST /documents/{id}/retry/` — retry a failed job; return `409` if already processing.

Never let clients set owner, object key, ingestion status, vector collection, or arbitrary Qdrant filters.

Example document response:
```json
{
  "id": "uuid",
  "title": "Biology - Cell Structure",
  "subject": "Biology",
  "size_bytes": 284100,
  "page_count": 12,
  "chunk_count": 38,
  "status": "READY",
  "created_at": "2026-10-25T08:00:00Z"
}
```

## Ask
`POST /ask/`

Request:
```json
{
  "question": "What are the main functions of mitochondria?",
  "document_ids": [],
  "top_k": 5
}
```

Rules:
- Require a non-empty, length-limited question.
- If `document_ids` are supplied, validate that every document belongs to the user and is `READY`.
- Clamp `top_k` to a safe server-defined range.
- Do not accept client-supplied context, owner IDs, prompts, collection names, or raw filters.
- Return a clear insufficient-context response if retrieval finds no usable evidence.
- Return a safe retryable error for provider outages.

Response:
```json
{
  "answer": "According to the uploaded notes, ...",
  "grounded": true,
  "insufficient_context": false,
  "sources": [
    {
      "document_id": "uuid",
      "document_title": "Biology - Cell Structure",
      "page": 4,
      "chunk_id": "uuid",
      "excerpt": "The mitochondrion is responsible for ..."
    }
  ],
  "request_id": "server-generated-id"
}
```

Build sources on the server from retrieved chunks. Do not trust the model to invent source IDs or page numbers.

## Optional history (later)
- `GET /conversations/`
- `POST /conversations/`
- `GET /conversations/{id}/messages/`
- `POST /conversations/{id}/messages/`

Scope every conversation to its owner.

## Health
- `GET /health/live/` — process alive.
- `GET /health/ready/` — required dependencies available without revealing secrets.

Status enum: `QUEUED`, `PROCESSING`, `READY`, `FAILED`, `DELETING`.
