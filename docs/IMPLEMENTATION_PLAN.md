# Implementation Plan

## Phase 0 — Verify model feasibility
- Confirm exact Gemma model, official runtime/API, credentials, quota, and terms.
- Verify generation support.
- Verify embedding support separately; select a compatible fallback if unavailable.
**Gate:** small test script successfully calls the chosen generation endpoint and, if supported, embedding endpoint.

## Phase 1 — Foundation
Create Django project/apps, environment-based settings, PostgreSQL, DRF, templates, static files, and health endpoints.
**Gate:** migrations and health check pass.

## Phase 2 — Auth and UI shell
Build responsive layout, navigation, login/register, CSRF/auth policy, empty states.
**Gate:** auth and ownership tests pass; mobile layout works.

## Phase 3 — Document library and R2
Create Document model, R2 storage service, upload/list/detail/update/delete API and UI. Validate PDF size/signature.
**Gate:** PDF stored privately and linked to the correct user.

## Phase 4 — Background processing
Add Celery/Redis, page extraction, chunking, status transitions, retries, and safe errors.
**Gate:** test PDF yields chunks with page metadata.

## Phase 5 — Vector indexing
Implement embedding adapter and Qdrant service, collection initialization, payload indexes, batch upserts, cleanup.
**Gate:** query vector dimension is validated and indexed chunks can be retrieved.

## Phase 6 — Grounded answering
Implement owner-scoped retrieval, context-limited prompt, Gemma adapter, sources, abstention, timeouts.
**Gate:** answerable questions cite retrieved passages; unanswerable questions abstain.

## Phase 7 — Ask UI
Build question composer, loading/error states, answer panel, source cards, optional document scope.
**Gate:** end-to-end flow works on mobile and desktop.

## Phase 8 — Security and quality
Add throttling, secure settings, prompt-injection defenses, access-isolation tests, logging/redaction.
**Gate:** cross-user access tests pass.

## Phase 9 — AWS deployment
Create Dockerfile/Compose, TLS, private networking, secrets, persistence, health checks, backups.
**Gate:** deployed smoke tests pass and restore is tested.

## Phase 10 — Evaluation
Create representative question set; measure retrieval relevance, groundedness, citation accuracy, abstention, latency, and cost. Tune chunking/top-k based on evidence. Add OCR/history only after baseline works.
