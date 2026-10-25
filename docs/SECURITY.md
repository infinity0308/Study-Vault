# Security and Privacy

## Authentication and authorization
- Require authentication for document and ask endpoints.
- Scope every document query by the current user.
- Check ownership for every document ID, source, retry, and delete action.
- Build Qdrant filters server-side; never accept raw filters from clients.
- Use CSRF protection for session-authenticated browser requests.
- Throttle login, upload, and ask endpoints.

## File safety
- Keep R2 bucket private.
- Enforce size limits and validate file signature, MIME, and extension.
- Use random object keys.
- Limit PDF extraction time, memory, and page count.
- Consider malware scanning/quarantine before production.
- Never render uploaded active content as trusted HTML.

## Secrets
- Put credentials in environment variables or a secrets manager.
- Commit `.env.example`, never `.env`.
- Restrict R2 credentials to required actions/bucket where possible.
- Never log API keys, signed URLs, private PDF text, or full prompts.

## RAG-specific risks
- PDF content is untrusted and may contain prompt injection.
- Retrieved text must never override system instructions or permission checks.
- Do not expose another user's chunks through retrieval, cache keys, or conversation history.
- Construct citations from server-side retrieval metadata.
- Explain that relevant document text may be sent to the configured model provider, subject to its terms and settings.

## Deployment hardening
- HTTPS, `DEBUG=False`, exact allowed hosts, trusted origins, secure cookies.
- Keep PostgreSQL, Redis, and Qdrant on a private network.
- Patch dependencies and use least-privilege service credentials.
- Back up databases and Qdrant; test restores.
- Use structured logs with request IDs and redaction.
- Define data retention and account deletion before public launch.
