# Roadmap

The current release is an end-to-end local MVP. These extensions are not yet implemented.

1. Add a larger held-out document corpus and measure retrieval relevance, citation support, abstention, and latency separately.
2. Add persistent dense vector storage and a measured reranking stage.
3. Move PDF parsing and ingestion to isolated background jobs with retry and idempotency controls.
4. Introduce document permissions, tenant isolation, audit trails, and deployment authentication.
5. Add streaming generation and conversation history after source-grounding behavior is tested.

Keep benchmark claims tied to a committed dataset and reproducible command. Avoid describing toy-fixture results as real-world accuracy.
