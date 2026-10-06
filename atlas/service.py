import threading
import time

from .answers import answer
from .retrieval import Retriever
from .store import Store
from .models import model_status
from .embeddings import encode


class Service:
    def __init__(self, db, semantic_model=None, ollama_model=None, ollama_url="http://localhost:11434"):
        self.store = Store(db)
        self.semantic_model = semantic_model
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self.lock = threading.RLock()
        self.retriever = None
        self.fingerprint = None
        self.cache_path = str(db) + ".vectors.sqlite3"

    def ingest(self, name, data):
        with self.lock:
            result = self.store.ingest(name, data)
            self.retriever = None
            return result

    def delete(self, identifier):
        with self.lock:
            result = self.store.delete(identifier)
            self.retriever = None
            return result

    def search(self, question, k=5):
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
            raise ValueError("Question must have 1–2,000 characters")
        if type(k) is not int or not 1 <= k <= 20:
            raise ValueError("k must be an integer between 1 and 20")
        start = time.perf_counter()
        with self.lock:
            fingerprint = self.store.fingerprint()
            if self.retriever is None or fingerprint != self.fingerprint:
                self.retriever = Retriever(self.store.records(), self.semantic_model, self.cache_path)
                self.fingerprint = fingerprint
            hits = self.retriever.search(question, k)
        return {"hits": hits, "latency_ms": round(1000 * (time.perf_counter() - start), 2),
                "retrieval": "bm25+dense+rrf" if self.semantic_model else "bm25"}

    def ask(self, question, k=5):
        start = time.perf_counter()
        results = self.search(question, k)
        return dict(answer(question, results["hits"], self.ollama_model, self.ollama_url),
                    latency_ms=results["latency_ms"], total_ms=round(1000 * (time.perf_counter() - start), 2),
                    retrieval=results["retrieval"])

    def status(self, check=False):
        import importlib.util
        models = model_status(self.semantic_model, self.ollama_model, self.ollama_url, check)
        if check and self.semantic_model and models["semantic_dependency"]:
            try:
                encode(self.semantic_model, ["model readiness check"])
            except ValueError as exc:
                models["errors"].append(str(exc))
                models["ready"] = False
        return dict(models, documents=len(self.store.documents()),
                    pdf_available=importlib.util.find_spec("pypdf") is not None,
                    retrieval="bm25+dense+rrf" if self.semantic_model else "bm25",
                    generation="ollama" if self.ollama_model else "evidence")
