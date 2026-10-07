# Architecture and decisions

The service owns a SQLite store and a lazy retrieval snapshot. Ingestion parses input before atomically inserting a document and its passages. SHA-256 content IDs make repeated ingestion idempotent. Deletion cascades to passages. A lock serializes service mutations and retrieval rebuilding; a document-ID fingerprint also detects external CLI changes on the next query.

Passages contain 160 words with 32-word overlap and never cross a PDF page. Indexed text normalizes whitespace. Citation IDs combine content hash, page, and chunk position. Text files use page 1. Original PDFs are not retained; the database stores extracted passages and document metadata.

BM25 uses an inverted index, token frequencies, length normalization (`k1=1.5`, `b=0.75`), stopword removal, Unicode words, and camel-case splitting. The first 50 positive BM25 matches and first 50 dense candidates above cosine 0.2 contribute `1/(60+rank)` to reciprocal rank fusion. Thresholds are heuristic, not calibrated confidence. Dense similarity is an in-memory linear scan.

Normalized embeddings are cached beside the index in `<db>.vectors.sqlite3`, keyed by model name and content hash. Unchanged content survives restarts without document re-encoding; query vectors are computed per request. Cache entries contain JSON numbers, not executable pickles. A changed model under the same name/path requires removing the disposable vector cache. Deleted content is removed from retrieval immediately; unused numeric cache entries remain until the cache is removed. The cache stores no original text.

Ollama receives a bounded ranked context as untrusted source data and a JSON schema. It selects short source IDs; the server validates them and attaches exact excerpts, document names and pages. At most four claims are accepted. Malformed or invalid citations get one retry, then a visible error. This avoids depending on models to reproduce hashes or quotes, but does not prove claims are supported or eliminate prompt injection.

The browser uses DOM textContent for source material. Host/Origin checks, bounded JSON bodies, local binding, and a non-root Docker user support local operation. PDF parsing is synchronous and has no worker resource isolation. These choices do not constitute multi-user production infrastructure.

Primary references: [Sentence Transformers](https://sbert.net/docs/package_reference/sentence_transformer/model.html), [Ollama generation](https://docs.ollama.com/api/chat), [SQLite](https://docs.python.org/3/library/sqlite3.html).
