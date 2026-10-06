import threading
import time

from .answers import answer
from .retrieval import Retriever
from .store import Store


class Service:
    def __init__(self, db, semantic_model=None, ollama_model=None, ollama_url="http://localhost:11434"):
        self.store = Store(db)
        self.semantic_model = semantic_model
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self.lock = threading.RLock()
        self.retriever = None

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
            if self.retriever is None:
                self.retriever = Retriever(self.store.records(), self.semantic_model)
            hits = self.retriever.search(question, k)
        return {"hits": hits, "latency_ms": round(1000 * (time.perf_counter() - start), 2),
                "retrieval": "bm25+dense+rrf" if self.semantic_model else "bm25"}

    def ask(self, question, k=5):
        results = self.search(question, k)
        return dict(answer(question, results["hits"], self.ollama_model, self.ollama_url),
                    latency_ms=results["latency_ms"], retrieval=results["retrieval"])
