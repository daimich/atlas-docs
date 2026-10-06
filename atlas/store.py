"""Transactional ingestion; page boundaries remain intact through chunking."""

import hashlib
import io
import sqlite3
from contextlib import contextmanager
from pathlib import Path

MAX_BYTES = 15 * 1024 * 1024


def chunks(text, size=160, overlap=32):
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require 0 <= overlap < size")
    words = text.split()
    for start in range(0, len(words), size - overlap):
        yield " ".join(words[start:start + size])
        if start + size >= len(words):
            break


def pages(name, data):
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("Install PDF support: pip install '.[pdf]'") from exc
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > 2000:
                raise ValueError("Encrypted PDFs and PDFs over 2,000 pages are unsupported")
            return [page.extract_text() or "" for page in reader.pages]
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not parse PDF") from exc
    if suffix not in {".txt", ".md"}:
        raise ValueError("Supported formats: .txt, .md, .pdf")
    try:
        return [data.decode("utf-8")]
    except UnicodeDecodeError as exc:
        raise ValueError("Text documents must be UTF-8") from exc


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, pages INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    page INTEGER NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            with db:
                yield db
        finally:
            db.close()

    def ingest(self, name, data):
        name = Path(name).name
        if not name or len(name) > 200:
            raise ValueError("Filename must have 1–200 characters")
        if len(data) > MAX_BYTES:
            raise ValueError("Document exceeds 15 MiB")
        identifier = hashlib.sha256(data).hexdigest()
        with self.connect() as db:
            existing = db.execute("SELECT * FROM documents WHERE id=?", (identifier,)).fetchone()
            if existing:
                return dict(existing, duplicate=True)
        extracted = pages(name, data)
        rows = [(f"{identifier}:{page}:{position}", identifier, page, position, text)
                for page, content in enumerate(extracted, 1)
                for position, text in enumerate(chunks(content))]
        if not rows:
            raise ValueError("No text extracted; scanned PDFs require OCR before ingestion")
        with self.connect() as db:
            inserted = db.execute("INSERT OR IGNORE INTO documents(id,name,pages) VALUES(?,?,?)",
                                  (identifier, name, len(extracted))).rowcount
            if inserted:
                db.executemany("INSERT INTO chunks VALUES(?,?,?,?,?)", rows)
        return {"id": identifier, "name": name, "pages": len(extracted), "chunks": len(rows), "duplicate": not bool(inserted)}

    def documents(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""
                SELECT d.*, COUNT(c.id) AS chunks FROM documents d
                LEFT JOIN chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY d.name
            """)]

    def records(self):
        with self.connect() as db:
            return [dict(row, search_text=row["text"]) for row in db.execute("""
                SELECT c.*, d.name FROM chunks c JOIN documents d ON d.id=c.document_id ORDER BY c.id
            """)]

    def delete(self, identifier):
        with self.connect() as db:
            return bool(db.execute("DELETE FROM documents WHERE id=?", (identifier,)).rowcount)
