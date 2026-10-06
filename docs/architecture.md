# Architecture and engineering decisions

The service owns a SQLite store and a lazy retrieval cache. Ingestion parses input before opening the write transaction, then atomically inserts the document and all of its page-specific passages. SHA-256 content identity makes repeated ingestion idempotent. A reentrant lock serializes ingestion/deletion with in-process cache rebuilding; the cache is invalidated on every service mutation. Out-of-process database edits require a server restart.

BM25 uses token frequencies, document frequencies, length normalization (`k1=1.5`, `b=0.75`), stopword removal, and camel-case splitting. The optional encoder computes normalized vectors. Ranked positive BM25 matches and the first 50 dense candidates with cosine at least 0.2 contribute `1/(60+rank)` to reciprocal rank fusion. The threshold is a heuristic. The demo is deliberately simple: no ANN index, learned reranker, or calibrated relevance classifier.

Each chunk belongs to exactly one PDF page. Chunk text normalizes whitespace, so validated quotes match the indexed passage, not necessarily byte-for-byte PDF layout. Text files use page 1. Citations are immutable chunk IDs constructed from the content hash, page number, and chunk position. No generated sentence is accepted without a valid citation ID and an exact quote of at least 12 characters. These checks establish provenance, not entailment or factual correctness.

The local Ollama adapter sends supplied evidence as untrusted data in the prompt. It accepts a bounded JSON response and validates every claim. This is a defense in depth measure, not a prompt-injection solution. A generator failure is visible to the caller.

The web interface escapes user-supplied text by using DOM `textContent`. HTTP requests require local Host values, same-origin requests when Origin is present, JSON content types, and bounded bodies. The server is a development interface, not production infrastructure. PDF extraction runs synchronously in-process; particularly complex untrusted PDFs should instead be isolated in a worker with CPU and memory limits.

## Challenges this implementation addresses

- Stable citations across retrieval and answer synthesis.
- Deduplication and transactional ingestion without orphaned chunks.
- Retrieval cache invalidation when documents are removed.
- Distinguishing retrieved evidence from generated interpretation.
- Deterministic model adapter tests without model downloads.

## Primary implementation references

- [Sentence Transformers encode API](https://sbert.net/docs/package_reference/sentence_transformer/model.html)
- [Ollama generate API](https://docs.ollama.com/api/generate)
- [Python sqlite3 documentation](https://docs.python.org/3/library/sqlite3.html)

## Scaling path

Move ingestion to a durable queue, add tenant-scoped metadata and authorization, store chunks and embeddings in PostgreSQL/pgvector, introduce hybrid candidate generation and a measured cross-encoder reranker, and evaluate answer support against a held-out labeled corpus before making quality claims.
