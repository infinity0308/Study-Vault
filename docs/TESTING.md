# Testing Strategy

## Unit tests
- PDF signature/size validation and filename sanitization.
- Text extraction, empty PDFs, page metadata, chunk overlap, stable IDs.
- Provider response validation, timeouts, and invalid credentials.
- Qdrant filter construction and vector dimension mismatch.
- Source formatting and status transitions.
- Deletion and retry idempotency.

## API tests
- Unauthenticated requests are rejected where required.
- Users can only list/read/update/delete their own documents.
- Upload rejects invalid, malformed, and oversized PDFs.
- Upload returns while processing is queued, not after full embedding.
- Clients cannot change owner, object key, status, or vector filters.
- Retry rejects jobs already processing.
- Ask rejects blank/oversized questions and unauthorized document scopes.
- No-context response contains no fabricated sources.
- Provider outage returns a safe retryable error.
- Deletion blocks access immediately and eventually removes R2 object and vectors.

## RAG evaluation
Create a small test set from representative notes. Each case should specify a question, expected key facts, source page(s), and at least a few unanswerable questions. Evaluate:
- Whether top-k retrieval contains the expected passage.
- Whether answer claims are supported by the retrieved context.
- Whether source cards map to real retrieved chunks.
- Whether the model abstains when context is insufficient.
- Latency, timeouts, and provider cost.

Do not evaluate only on the examples used to tune the prompt.

## Integration tests
Mock external services for normal CI. Keep opt-in integration tests using a dedicated test R2 bucket and Qdrant collection. Never allow tests to delete production data.

## Manual smoke test
1. Sign in.
2. Upload a text-based PDF.
3. Wait for `READY`.
4. Ask a question explicitly answered by the PDF.
5. Check the source excerpt and page.
6. Ask something absent from the notes and confirm abstention.
7. Attempt cross-user access by changing an ID.
8. Delete a document and verify object/vector cleanup.
9. Test mobile layout.
10. Disable the model provider temporarily and verify the error state.
