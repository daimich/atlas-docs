"""Opt-in acceptance test using real embeddings and an already pulled Ollama model."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas.service import Service
from atlas.web import make_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--semantic-model', default='sentence-transformers/all-MiniLM-L6-v2')
    parser.add_argument('--ollama-model', default='qwen2.5:1.5b')
    parser.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / 'index.sqlite3'
        service = Service(db, args.semantic_model, args.ollama_model, args.ollama_url)
        service.ingest('notice.md', b'Either party may terminate the agreement with thirty days of written notice.')
        service.ingest('office.md', b'The office cafeteria is open from noon to two in the afternoon.')
        question = 'How much written notice is required to terminate the agreement?'
        health = service.status(check=True)
        assert health['ready'], health
        assert service.search(question)['hits'][0]['name'] == 'notice.md'
        with sqlite3.connect(str(db) + '.vectors.sqlite3') as cache:
            assert cache.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0] == 2
        # Reopen the persisted index and run generation through the actual HTTP API.
        restarted = Service(db, args.semantic_model, args.ollama_model, args.ollama_url)
        server = make_server(restarted, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/ask',
                data=json.dumps({'question': question, 'k': 2}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=300) as response:
                result = json.load(response)
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
        assert result['mode'] == 'ollama' and not result['abstained'], result
        by_id = {item['id']: item for item in result['evidence']}
        assert result['claims']
        for claim in result['claims']:
            assert claim['quote'] in by_id[claim['citation']]['text']
            assert claim['name'] == 'notice.md' and claim['page'] == 1, claim
        answer = ' '.join(item['text'] for item in result['claims']).lower()
        assert 'thirty' in answer or '30' in answer, result
        print(json.dumps({'passed': True, 'semantic_model': args.semantic_model,
                          'ollama_model': args.ollama_model, 'result': result}, indent=2))


if __name__ == '__main__':
    main()
