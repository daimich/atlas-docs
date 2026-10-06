# JSON API

Default base: `http://127.0.0.1:8080`. Failures return an `error` string. Validation errors use HTTP 400; unavailable or invalid configured model responses use 503. The local server has no accounts.

| Method | Path | Input / response |
|---|---|---|
| GET | `/api/health` | Process health: `{ "status": "ok" }` |
| GET | `/api/status` | Document count, PDF availability, model configuration, retrieval/generation mode |
| GET | `/api/documents` | Document IDs, names, pages, timestamps, chunk counts |
| POST | `/api/ingest` | `{ "name": "contract.md", "base64": "..." }` |
| POST | `/api/search` | `{ "question": "payment terms", "k": 5 }`; ranked passages |
| POST | `/api/ask` | Same input; mode, abstention, cited claims, source evidence |
| POST | `/api/delete` | `{ "id": "document-sha256" }`; deleted boolean |

```bash
curl http://127.0.0.1:8080/api/ask -H 'Content-Type: application/json' -d '{"question":"What are the payment terms?","k":3}'
```

Questions allow 1–2,000 nonblank characters; `k` is an integer from 1 to 20. Request bodies must be JSON objects, at most 22 MiB including base64; decoded uploads must be at most 15 MiB. Filenames are reduced to their basename. Ingestion accepts uploaded content, never a server-side path.

`latency_ms` measures retrieval (including cache construction); `total_ms` on answers includes generation. Evidence mode returns excerpts labeled as retrieved passages. Ollama mode returns interpretations with immutable citation IDs, exact server-attached quotes, document names, and page references. Quote validity does not establish entailment. Generation uses at most 12,000 source characters, with at most 6,000 per source, in retrieval order; full retrieved evidence is also returned.

`/api/status` is a lightweight configuration check; `ollama_ready: null` means the endpoint has not been probed. Use `python -m atlas doctor` to load the embedding model and test Ollama readiness. Model setup failures return a nonzero CLI exit status.
