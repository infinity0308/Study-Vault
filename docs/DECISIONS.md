# Decisions and Open Questions

## Fixed by the initial brief
- Python and Django backend.
- Django REST Framework API.
- Custom polished responsive website.
- Cloudflare R2 for original PDFs.
- Qdrant vector database.
- Docker deployment on AWS.
- Google Gemma is the desired answer model.
- Main features: upload learning PDFs and ask questions grounded in uploaded material.

## Proposed defaults
| Topic | Proposal | Reason |
|---|---|---|
| Name | StudyVault (placeholder) | Easy to rename |
| Database | PostgreSQL | Reliable relational source of truth |
| Worker | Celery + Redis | Ingestion should not block web requests |
| UI | Django templates + responsive CSS, optional HTMX | Avoids separate frontend stack initially |
| Auth | Django session auth for same-origin UI | Straightforward with CSRF |
| API prefix | `/api/v1/` | Versionable |
| R2 visibility | Private | Protects study materials |
| Chat history | Later | Reduce initial complexity |
| OCR | Later | Avoid extra resource burden |

## Resolve before coding
1. **Exact Gemma endpoint/model:** confirm official availability, model ID, SDK, quotas, and terms.
2. **Embedding support:** confirm the same model/runtime offers embeddings. Otherwise explicitly choose a separate embedding model/runtime.
3. **Sharing model:** current assumption is each user sees only their own PDFs. Classroom/shared libraries need explicit group permissions.
4. **Limits:** proposed initial PDF limit is 25 MB; tune based on server capacity.
5. **Quotas/cost:** define request limits, maximum chunks, timeouts, and upload quotas.
6. **PDF scope:** MVP supports PDFs with extractable text; OCR is later.
7. **AWS size:** one VM may be okay for a demo, but Django, worker, Qdrant, Redis, and PostgreSQL compete for memory/disk. Measure and separate services as needed.

## Change log
- 2026-10-25: Initial specification drafted.
