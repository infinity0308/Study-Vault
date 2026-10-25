# Deployment Plan

## Target services
A small AWS EC2 VM with Docker Compose can host Nginx, Django/Gunicorn, Celery worker, PostgreSQL, Redis, and Qdrant for an MVP. Cloudflare R2 stores PDFs externally. For production or growing traffic, consider managed PostgreSQL, separate worker capacity, and service backups.

## Environment variables
Create `.env.example` with placeholders like:
```dotenv
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://studyvault:change-me@db:5432/studyvault
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=study_chunks_v1
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_REGION=auto
LLM_PROVIDER=google_gemma
GEMMA_API_KEY=
GEMMA_MODEL=
EMBEDDING_PROVIDER=
EMBEDDING_MODEL=
EMBEDDING_DIMENSION=
CHUNK_TARGET_TOKENS=850
CHUNK_OVERLAP_TOKENS=120
RAG_TOP_K=5
MAX_UPLOAD_MB=25
```
These are proposed app variable names, not guaranteed names required by Google's SDK. Adapt provider code to the selected official API.

## Docker and networking
- Pin image/dependency versions; run app as non-root where practical.
- Persist PostgreSQL and Qdrant data with volumes.
- Do not bake secrets into images.
- Run web and worker separately.
- Apply migrations as a controlled release step.
- Public inbound: 80/443 and restricted SSH or AWS Systems Manager.
- Keep PostgreSQL 5432, Redis 6379, Qdrant 6333/6334, and app ports private.
- Never expose Qdrant directly to the public internet.

## R2 setup
1. Create a bucket and keep public access disabled.
2. Create scoped API credentials.
3. Configure endpoint, account ID, key, secret, bucket, and region.
4. Test upload/download/delete through an S3-compatible SDK.
5. Set lifecycle/retention expectations.

## Production checklist
- `DEBUG=False`, strong secret key, exact `ALLOWED_HOSTS`, CSRF origins.
- HTTPS and secure cookies; enable HSTS only after HTTPS works reliably.
- Health checks, structured logs, error monitoring, timeouts, and backups.
- Qdrant collection dimension matches actual embedding output.
- Smoke test login, upload, processing, ask, and deletion after deploy.
- Test restoring backups before onboarding users.
