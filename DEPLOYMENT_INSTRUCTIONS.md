# Hosting & Deployment Guide for StudyVault

StudyVault is packaged and ready to run with Docker Compose on any Linux host (e.g. AWS EC2, DigitalOcean Droplet, Hetzner, or local server).

## 1. Prerequisites

- Docker and Docker Compose (v2.20+) installed on the host machine.
- Ports `80` (and `443` if using TLS) open in your firewall / AWS Security Group.

---

## 2. Configuration (`.env`)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and fill in:

### A. Core Settings
```dotenv
DEBUG=False
SECRET_KEY=change-this-to-a-very-secure-random-string
ALLOWED_HOSTS=localhost,127.0.0.1,your-server-ip,yourdomain.com
```

### B. Cloudflare R2 (External Private PDF Storage)
1. In Cloudflare Dashboard, navigate to **R2 Storage** &rarr; **Create Bucket** (name: `studyvault-docs`).
2. Keep public access **disabled** (bucket remains strictly private).
3. Under **Manage R2 API Tokens**, create a new API Token with **Object Read & Write** permissions scoped to your bucket.
4. Set in `.env`:
   ```dotenv
   R2_ACCOUNT_ID=<your-account-id>
   R2_ACCESS_KEY_ID=<your-token-access-key-id>
   R2_SECRET_ACCESS_KEY=<your-token-secret-access-key>
   R2_BUCKET_NAME=studyvault-docs
   R2_ENDPOINT_URL=https://<your-account-id>.r2.cloudflarestorage.com
   ```
*(Note: If R2 credentials are blank or omitted during local testing, StudyVault automatically falls back to secure local media storage).*

### C. Google Gemma & Embeddings API
1. Get an API key from [Google AI Studio](https://aistudio.google.com/) or Google Cloud Vertex AI.
2. Set in `.env`:
   ```dotenv
   LLM_PROVIDER=google_gemma
   GEMMA_API_KEY=<your-google-api-key>
   GEMMA_MODEL=gemma-2-9b-it
   EMBEDDING_PROVIDER=google_genai
   EMBEDDING_MODEL=text-embedding-004
   EMBEDDING_DIMENSION=768
   ```

---

## 3. Starting the Services

To build and launch all containers (`web`, `worker`, `db`, `redis`, `qdrant`, `nginx`):

```bash
docker compose up -d --build
```

The `web` container automatically:
1. Waits for PostgreSQL to be healthy.
2. Runs all database migrations (`python manage.py migrate`).
3. Collects and minifies static files (`python manage.py collectstatic`).
4. Launches Gunicorn with 3 workers.

The `worker` container automatically starts Celery to process PDF uploads, text chunking, and Qdrant vector indexing asynchronously.

---

## 4. Creating an Administrator Account

To access the Django operational admin at `http://your-server/admin/`:

```bash
docker compose exec web python manage.py createsuperuser
```

---

## 5. Health Monitoring & Checks

You can monitor the live status of the deployment anytime:

- **Liveness Probe**: `http://your-server/health/live/`
- **Readiness Probe**: `http://your-server/health/ready/` (checks DB, Redis task queue, and Qdrant)
- **Container status**:
  ```bash
  docker compose ps
  ```
- **Service logs**:
  ```bash
  docker compose logs -f web worker
  ```

---

## 6. Upgrades & Maintenance

To pull the latest changes, rebuild, and re-apply migrations:

```bash
git pull
docker compose up -d --build
```
