# Atlas

**Document intelligence with evidence you can inspect.**

Atlas uploads and indexes documents, searches their passages, and answers with original document/page references. It works offline in evidence mode, with optional semantic retrieval and local Ollama generation. Version 0.2 adds persistent embeddings, model diagnostics, live index refresh, and browser, Docker, and real-model acceptance tests.

The supported scope is a single-user local application. Generated claims include exact source excerpts; citation validity does not establish that the interpretation is correct.

## Start locally

Requires Python 3.11+. After cloning or extracting the source archive:

```bash
git clone https://github.com/daimich/atlas-docs.git
cd atlas-docs
python -m venv .venv
source .venv/bin/activate
python -m pip install '.[pdf]'
python -m atlas ingest examples/documents
python -m atlas doctor
python -m atlas serve
```

On Windows, activate with `.venv\Scripts\activate` instead. Open **http://127.0.0.1:8080**, upload a document, and ask “How much notice is required for termination?” Text/Markdown mode also runs directly from source without third-party dependencies. If you downloaded an archive, skip cloning and start in its extracted project folder.

```bash
python -m atlas ask "What is the liability limit?"
python -m atlas list
python -m atlas delete DOCUMENT_ID
```

The installed `atlas` command is equivalent to `python -m atlas`. CLI changes appear in the running server on its next query. Data lives in `.atlas/index.sqlite3`; the global `--db /path/to/index.sqlite3` option selects another workspace.

## What works

| Capability | Behavior |
|---|---|
| Documents | UTF-8 text/Markdown and text-based PDFs with the `pdf` extra |
| Provenance | Content-hash IDs and page-specific passages; chunks never cross PDF pages |
| Retrieval | BM25 inverted index; optional normalized dense embeddings and reciprocal rank fusion |
| Answers | Retrieved excerpts by default; optional generated claims with exact source references |
| Persistence | Transactional SQLite ingestion, deduplication, cascading deletion, live refresh |
| Embeddings | Content-addressed SQLite cache reused across restarts and unchanged documents |
| Interface | Browser upload/search/delete, CLI, JSON API, and model readiness diagnostics |
| Verification | Regression tests, Chromium workflow, Docker restart test, real-model workflow |

PDFs must be unencrypted, at most 15 MiB and 2,000 pages. Scanned PDFs require OCR before uploading. Text files use page 1 as their citation anchor. Retrieval scores are diagnostics, not confidence probabilities.

## Enable AI

Install [Ollama](https://ollama.com/download) and start it (`ollama serve` if the desktop app is not already running). In another terminal:

```bash
ollama pull qwen2.5:1.5b
python -m pip install '.[semantic,pdf]'
python -m atlas --semantic-model sentence-transformers/all-MiniLM-L6-v2 --ollama-model qwen2.5:1.5b doctor
python -m atlas --semantic-model sentence-transformers/all-MiniLM-L6-v2 --ollama-model qwen2.5:1.5b serve
```

Semantic retrieval and generation can be enabled independently. Embedding weights download on first use; a local model directory also works. `doctor` loads the embedding model and checks that Ollama has the requested model, exiting with a nonzero status when setup is incomplete. Model size and hardware determine latency; the small model above is an acceptance-test baseline, not a quality guarantee.

The CLI also accepts `SEMANTIC_MODEL`, `OLLAMA_MODEL`, and `OLLAMA_URL` environment variables. `--ollama-url` defaults to `http://localhost:11434`. Documents are sent to the endpoint you configure; the default runs on your machine.

Generation uses bounded source context and a JSON schema. Unknown citations, malformed output, and unavailable models produce visible errors. Exact excerpts are attached by the server from the cited passages. Inspect them before relying on an answer: a model can still misinterpret a source or abstain when it contains an answer.

## Docker

```bash
docker compose up --build -d
```

Open **http://127.0.0.1:8080**. PDF support and fictional demo documents are included. Named volumes preserve documents and caches when containers are replaced. `docker compose down` keeps them; `docker compose down -v` deletes them.

For the AI profile, create a local `.env` file with:

```dotenv
ENABLE_SEMANTIC=1
SEMANTIC_MODEL=sentence-transformers/all-MiniLM-L6-v2
OLLAMA_MODEL=qwen2.5:1.5b
```

Then run:

```bash
docker compose --profile ai up --build -d
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose exec atlas doctor
```

Compose reads `.env`; the Python CLI does not load it automatically. The AI image downloads CPU dependencies and model weights and needs more disk space and memory than the default image. Default Docker startup and persistence are tested in CI; the optional Compose AI profile combines the same adapters tested by the separate real-model workflow.

## Verification and limits

```bash
python -m unittest discover -s tests -v
python -m atlas ingest examples/documents
python -m atlas eval
```

`eval` reports Recall@5 and MRR@5 on six fictional queries. Use an index containing only the demo corpus. This is a regression fixture, not evidence of general document-answering accuracy. See [validation](docs/validation.md), [API](docs/api.md), [architecture](docs/architecture.md), and [remaining extensions](docs/roadmap.md).

The server is for local use: loopback by default, localhost Host/Origin checks, no accounts, tenant isolation, TLS, or remote deployment gateway. PDF parsing is synchronous. Records and dense vectors reside in memory while serving; dense search is linear in corpus size. Scanned-PDF OCR, large-scale search, and multi-user hosting are outside this release.

MIT licensed. All example documents are fictional.
