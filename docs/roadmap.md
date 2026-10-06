# Remaining extensions

Version 0.2 completes the documented local upload → retrieve → answer → inspect/delete workflow, including optional model adapters, persistent embeddings, diagnostics and automated acceptance checks. The following are separate future extensions:

1. A larger held-out corpus measuring relevance, answer support, abstention and latency independently.
2. OCR for scanned PDFs and isolated background parsing jobs.
3. Reranking and an ANN/vector database for larger corpora.
4. Authenticated multi-user hosting, per-document permissions and audit trails.
5. Streaming generation and conversation history.

The tiny bundled evaluation is a regression fixture. Do not describe its results as real-world accuracy.
