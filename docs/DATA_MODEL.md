# Data Model

PostgreSQL is the application source of truth. R2 stores PDF bytes; Qdrant stores vector points.

## Document model
Suggested `library.Document` fields:
- `id`: UUID primary key
- `owner`: FK to Django user
- `title`, `subject` (optional), `description`
- `original_filename`: sanitized display name
- `object_key`: private R2 key, never a public URL
- `content_type`, `size_bytes`
- `page_count`, `chunk_count`
- `status`: `QUEUED`, `PROCESSING`, `READY`, `FAILED`, `DELETING`
- `failure_code`, safe `failure_message`
- `created_at`, `updated_at`, `processed_at`
- optional `deleted_at` tombstone

Choose the user model before the first migration. If custom email-based users are needed, configure `AUTH_USER_MODEL` from the beginning.

## Optional question history
`assistant.Question`: UUID, owner, question, answer, grounded flag, timestamp, optional latency/model version.

`assistant.AnswerSource`: question FK, document FK, chunk ID, page number, excerpt. Avoid retaining full prompts by default.

## Qdrant payload example
```json
{
  "owner_id": "user-uuid",
  "document_id": "document-uuid",
  "chunk_id": "chunk-uuid",
  "page": 4,
  "text": "The mitochondrion is responsible for ...",
  "embedding_model": "configured-model-version"
}
```

Add payload indexes for `owner_id` and `document_id`. Never accept a filter from the browser. Keeping chunk text in payload is convenient but duplicates private text; decide this deliberately.

## R2 object key
`users/{user_uuid}/documents/{document_uuid}/original.pdf`

Use UUIDs rather than original filenames as object identity. Keep bucket private and generate short-lived signed URLs only when necessary.

## Embedding compatibility
All vectors in one collection must have the same dimensions and compatible model/version. Derive vector size from actual provider output. For a model migration, create a new collection and re-embed instead of mixing vectors.
