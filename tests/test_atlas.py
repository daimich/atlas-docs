import base64
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from atlas.answers import answer, validate_claims
from atlas.retrieval import Retriever, tokens
from atlas.service import Service
from atlas.store import chunks
from atlas.web import make_server


class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Service(Path(self.temp.name) / "index.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_ingestion_deduplicates_by_content(self):
        first = self.service.ingest("contract.md", b"Termination requires thirty days notice.")
        second = self.service.ingest("renamed.md", b"Termination requires thirty days notice.")
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(self.service.store.documents()), 1)

    def test_page_references_survive_chunking(self):
        with patch("atlas.store.pages", return_value=["First page notice " * 200, "Second page retention"]):
            self.service.ingest("contract.pdf", b"fake PDF; parser is mocked")
        records = self.service.store.records()
        self.assertEqual({r["page"] for r in records}, {1, 2})
        self.assertTrue(all("Second" not in r["text"] for r in records if r["page"] == 1))

    def test_overlap_and_no_redundant_final_chunk(self):
        result = list(chunks(" ".join(str(i) for i in range(10)), size=6, overlap=2))
        self.assertEqual(result, ["0 1 2 3 4 5", "4 5 6 7 8 9"])
        with self.assertRaises(ValueError):
            list(chunks("hello", size=2, overlap=2))

    def test_empty_or_invalid_document_rejected(self):
        for name, data in [("empty.md", b""), ("binary.md", b"\xff"), ("code.exe", b"content")]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.service.ingest(name, data)
        self.assertEqual(self.service.store.documents(), [])

    def test_real_pdf_extraction_when_pdf_extra_is_installed(self):
        import importlib.util
        if importlib.util.find_spec("pypdf") is None:
            self.skipTest("Optional PDF extra is not installed")
        content = b"BT /F1 12 Tf 50 700 Td (Termination requires thirty days notice.) Tj ET"
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
                   b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                   b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
                   b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                   b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
        data = b"%PDF-1.4\n"
        offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(data))
            data += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
        xref = len(data)
        data += b"xref\n0 6\n0000000000 65535 f \n"
        data += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        data += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
        self.service.ingest("contract.pdf", data)
        hit = self.service.search("termination")["hits"][0]
        self.assertEqual(hit["page"], 1)
        self.assertIn("thirty days", hit["text"])

    def test_search_returns_cited_evidence_and_abstains_without_overlap(self):
        self.service.ingest("contract.md", b"Payment must be made within forty-five days.")
        self.service.ingest("security.md", b"Audit logs retained for a year.")
        result = self.service.ask("payment")
        self.assertEqual(result["claims"][0]["name"], "contract.md")
        self.assertEqual(result["claims"][0]["page"], 1)
        self.assertTrue(self.service.ask("intergalactic pineapple")["abstained"])

    def test_delete_invalidates_retrieval_and_cascades(self):
        document = self.service.ingest("a.md", b"payment terms")
        self.assertTrue(self.service.search("payment")["hits"])
        self.assertTrue(self.service.delete(document["id"]))
        self.assertEqual(self.service.search("payment")["hits"], [])
        self.assertEqual(self.service.store.records(), [])

    def test_query_input_limits(self):
        for question, k in [("", 1), (None, 1), ("x", 0), ("x", True), ("x" * 2001, 1)]:
            with self.assertRaises(ValueError):
                self.service.search(question, k)

    def test_citation_validation_rejects_fabrication(self):
        evidence = [{"id": "a", "name": "contract.md", "page": 2, "text": "Payment is due in thirty days."}]
        claim = {"text": "Thirty days", "citation": "a", "quote": "Payment is due in thirty days."}
        good = validate_claims({"abstain": False, "claims": [claim]}, evidence)
        self.assertEqual(good[0]["page"], 2)
        for mutated in [dict(claim, citation="unknown"), dict(claim, quote="Payment is due in sixty days.")]:
            with self.assertRaises(ValueError):
                validate_claims({"abstain": False, "claims": [mutated]}, evidence)
        with self.assertRaises(ValueError):
            validate_claims({"abstain": True, "claims": [claim]}, evidence)

    def test_ollama_adapter_request_and_response(self):
        hit = {"id": "a", "name": "contract.md", "page": 1, "text": "Payment is due in thirty days."}
        payload = {"abstain": False, "claims": [{"text": "Thirty days", "citation": "a", "quote": hit["text"]}]}
        with patch("urllib.request.urlopen") as mocked:
            mocked.return_value.__enter__.return_value.read.return_value = json.dumps({"response": json.dumps(payload)}).encode()
            result = answer("When?", [hit], "local-model")
        self.assertEqual(result["mode"], "ollama")
        request = mocked.call_args.args[0]
        self.assertFalse(json.loads(request.data)["stream"])

    def test_dense_fusion_adapter_with_fake_encoder(self):
        # No downloads in tests: verify protocol and ranking with deterministic vectors.
        import sys
        import types
        class Vector(list):
            def __matmul__(self, other):
                return sum(a * b for a, b in zip(self, other))
        class Encoder:
            def __init__(self, *args, **kwargs):
                pass
            def encode(self, texts, **kwargs):
                return [Vector([1, 0]) if "payment" in t or "invoice" in t else Vector([0, 1]) for t in texts]
        with patch.dict(sys.modules, {"sentence_transformers": types.SimpleNamespace(SentenceTransformer=Encoder)}):
            engine = Retriever([{"id": "a", "search_text": "payment"}, {"id": "b", "search_text": "security"}], "fake")
            self.assertEqual(engine.search("invoice")[0]["id"], "a")

    def test_fixture_retrieval(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "examples/documents").glob("*.md"):
            self.service.ingest(path.name, path.read_bytes())
        for case in json.loads((root / "examples/evaluation.json").read_text()):
            with self.subTest(question=case["question"]):
                self.assertIn(case["document"], [h["name"] for h in self.service.search(case["question"])["hits"]])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(Service(Path(self.temp.name) / "index.db"), 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, data=None, headers=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
                                         headers={"Content-Type": "application/json", **(headers or {})})
        return urllib.request.urlopen(request)

    def test_http_ingest_and_ask(self):
        with self.request("/api/ingest", {"name": "demo.md", "base64": base64.b64encode(b"Termination requires thirty days notice.").decode()}) as response:
            self.assertEqual(response.status, 200)
        with self.request("/api/ask", {"question": "termination"}) as response:
            self.assertEqual(json.load(response)["claims"][0]["name"], "demo.md")

    def test_cross_origin_and_invalid_json(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/ask", {"question": "x"}, {"Origin": "https://evil.example"})
        self.assertEqual(caught.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/ask", [])
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
