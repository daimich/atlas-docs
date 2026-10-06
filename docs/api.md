# JSON API

The default base URL is `http://127.0.0.1:8080`. JSON responses contain an `error` string for request failures. The same-origin localhost demo has no user authentication.

| Method | Path | Body / response |
|---|---|---|
| GET | `/api/health` | `{ "status": "ok" }` |
| GET | `/api/documents` | Document IDs, names, pages, timestamps, chunk counts |
| POST | `/api/ingest` | `{ "name": "contract.md", "base64": "..." }` |
| POST | `/api/search` | `{ "question": "payment terms", "k": 5 }`; returns hits and retrieval latency |
| POST | `/api/ask` | Same input; returns mode, abstention, claims, and evidence |
| POST | `/api/delete` | `{ "id": "document-sha256" }`; returns deleted boolean |

```bash
curl http://127.0.0.1:8080/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What are the payment terms?","k":3}'
```

Questions are limited to 2,000 characters; `k` must be an integer from 1 to 20. Bodies must be JSON objects. Upload requests are bounded to 22 MiB including base64 overhead; decoded files must be at most 15 MiB. Filenames are reduced to their basename. Ingestion accepts content, never a server-side file path.

Scores are retrieval diagnostics, not confidence probabilities. `latency_ms` measures retrieval, including cache construction on the first query, and excludes optional generation time. In default evidence mode, claims are labeled retrieved passages rather than synthesized answers.
