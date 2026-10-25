# Google Gemma API and Model Setup

## First, identify the correct runtime
“Gemma API” can refer to different model catalogs and serving options. Model availability and supported operations can change. Check the current official Google AI developer documentation/model catalog and the official Gemma documentation before choosing an endpoint.

1. Sign in to the official Google AI developer platform / Google AI Studio.
2. Check whether the exact Gemma model you want is available through that platform. If not, follow the current official instructions for a supported Google runtime/hosting option.
3. Follow that platform's current key/project setup instructions.
4. Check terms, quotas, regional availability, request limits, and supported SDK.
5. Store credentials in `.env` locally and a protected environment/secrets manager on AWS.
6. Test a tiny standalone request before integrating with Django.

Do not assume a key for one Google API automatically grants access to every Gemma model/runtime. Do not copy an old model ID or SDK method without checking current documentation.

## Generation and embeddings are different
- **Generation** returns text.
- **Embedding** returns a numeric vector used for similarity search.

A model that generates text does not automatically have an embedding endpoint. Verify the exact Gemma model/runtime supports embeddings. If it does not, use a documented embedding model/runtime for vectors and Gemma for answer generation. This is a practical, explicit fallback—not a fake Gemma embedding implementation.

## Internal provider interface
```python
class EmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        # Return one vector per input and validate dimensions.
        raise NotImplementedError


class AnswerProvider:
    def generate_answer(self, *, question: str, context: str) -> str:
        # Generate an answer grounded in supplied excerpts.
        raise NotImplementedError
```
These are application-level interfaces, not official SDK signatures. The concrete implementation must follow the selected provider's current documentation.

## Suggested configuration
```dotenv
LLM_PROVIDER=google_gemma
GEMMA_API_KEY=
GEMMA_MODEL=
EMBEDDING_PROVIDER=
EMBEDDING_MODEL=
EMBEDDING_DIMENSION=
```

Missing credentials should cause a clear configuration error, not fake answers or vectors.

## Low-storage laptop advice
- If using a hosted API, do not download large model weights.
- Run only required Docker services and use a small test PDF initially.
- Monitor Docker disk usage; avoid destructive volume-pruning commands unless you understand which data will be removed.
- Test embedding dimensions and provider failures before indexing a large collection.

## Checklist
- [ ] Exact model ID and runtime confirmed.
- [ ] Generation operation verified.
- [ ] Embedding operation verified, or fallback selected.
- [ ] Vector dimension and limits confirmed.
- [ ] API key stored outside source control.
- [ ] Successful request tested.
- [ ] Invalid key and timeout behavior tested.
- [ ] Decision recorded in `DECISIONS.md`.
