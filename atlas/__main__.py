import argparse
import json
import os
from pathlib import Path

from .service import Service
from .web import make_server


def main():
    parser = argparse.ArgumentParser(description="Atlas document intelligence")
    parser.add_argument("--db", default=".atlas/index.sqlite3")
    parser.add_argument("--semantic-model", default=os.environ.get("SEMANTIC_MODEL"), help="Sentence Transformers model path or ID")
    parser.add_argument("--ollama-model", default=os.environ.get("OLLAMA_MODEL"), help="Use a locally installed Ollama model for generation")
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("path", type=Path)
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--k", type=int, default=5)
    sub.add_parser("list")
    delete = sub.add_parser("delete")
    delete.add_argument("id")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--bind", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("--dataset", type=Path, default=Path("examples/evaluation.json"))
    sub.add_parser("doctor")
    args = parser.parse_args()
    try:
        service = Service(args.db, args.semantic_model, args.ollama_model, args.ollama_url)
        if args.command == "doctor":
            status = service.status(check=True)
            print(json.dumps(status, indent=2))
            if not status["ready"]:
                parser.exit(1)
        elif args.command == "ingest":
            if not args.path.exists():
                raise ValueError(f"Input path does not exist: {args.path}")
            if args.path.is_file() and args.path.suffix.lower() not in {".txt", ".md", ".pdf"}:
                raise ValueError("Supported formats: .txt, .md, .pdf")
            paths = sorted(args.path.rglob("*")) if args.path.is_dir() else [args.path]
            results = [service.ingest(path.name, path.read_bytes()) for path in paths
                       if path.is_file() and not path.is_symlink() and path.suffix.lower() in {".txt", ".md", ".pdf"}]
            if not results:
                raise ValueError("No supported documents found")
            print(json.dumps(results, indent=2))
        elif args.command == "list":
            print(json.dumps(service.store.documents(), indent=2))
        elif args.command == "delete":
            print(json.dumps({"deleted": service.delete(args.id)}))
        elif args.command == "ask":
            print(json.dumps(service.ask(args.question, args.k), indent=2))
        elif args.command == "serve":
            server = make_server(service, args.port, args.bind)
            print(f"Atlas → http://127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        elif args.command == "eval":
            dataset = json.loads(args.dataset.read_text())
            results = []
            reciprocal = 0
            for case in dataset:
                result = service.search(case["question"], 5)
                names = [r["name"] for r in result["hits"]]
                rank = next((i for i, name in enumerate(names, 1) if name == case["document"]), None)
                reciprocal += 1 / rank if rank else 0
                results.append({"question": case["question"], "rank": rank, "latency_ms": result["latency_ms"]})
            count = len(results)
            print(json.dumps({"queries": count, "recall_at_5": sum(r["rank"] is not None for r in results) / max(1, count),
                              "mrr_at_5": reciprocal / max(1, count), "results": results}, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
