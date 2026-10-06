import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from atlas.service import Service
from atlas.models import generate_claims, ModelError, model_request
from atlas.embeddings import vectors_for


class RegressionTests(unittest.TestCase):
    def test_missing_input_is_a_cli_failure(self):
        result = subprocess.run([sys.executable, '-m', 'atlas', 'ingest', '/nonexistent/document.md'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not exist', result.stderr)

    def test_cli_mutations_invalidate_running_service(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'index.db'
            first, second = Service(db), Service(db)
            doc = first.ingest('a.md', b'Termination requires thirty days notice.')
            self.assertTrue(first.search('termination')['hits'])
            second.delete(doc['id'])
            self.assertFalse(first.search('termination')['hits'])
            second.ingest('b.md', b'Zebras live in the savanna.')
            self.assertTrue(first.search('zebras')['hits'])

    def test_source_quote_is_attached_from_evidence(self):
        evidence = [{'id': 'long-document-id', 'text': 'Payment is due in thirty days.'}]
        payload = {'abstain': False, 'claims': [{'text': 'Thirty days.', 'citation': 'S1'}]}
        with patch('atlas.models.model_request', return_value={'response': json.dumps(payload)}):
            result = generate_claims('When?', evidence, 'model', 'http://localhost:11434')
        self.assertEqual(result['claims'][0]['citation'], 'long-document-id')
        self.assertEqual(result['claims'][0]['quote'], evidence[0]['text'])

    def test_invalid_citation_retries_and_remains_an_error(self):
        evidence = [{'id': 'x', 'text': 'Payment is due in thirty days.'}]
        payload = {'abstain': False, 'claims': [{'text': 'Wrong', 'citation': 'S2'}]}
        with patch('atlas.models.model_request', return_value={'response': json.dumps(payload)}) as request:
            with self.assertRaises(ModelError):
                generate_claims('When?', evidence, 'model', 'http://localhost:11434')
        self.assertEqual(request.call_count, 2)

    def test_model_unavailable_has_actionable_error(self):
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('connection refused')):
            with self.assertRaisesRegex(ModelError, 'ollama serve'):
                model_request('http://localhost:11434', '/api/generate', {})

    def test_persistent_vector_cache_only_encodes_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / 'vectors.db'
            with patch('atlas.embeddings.encode', side_effect=lambda model, texts: [[1.0, 0.0] for _ in texts]) as encoder:
                vectors_for('model', ['alpha', 'beta'], cache)
                vectors_for('model', ['alpha', 'beta'], cache)
                vectors_for('model', ['alpha', 'gamma'], cache)
                self.assertEqual(encoder.call_count, 2)
                self.assertEqual(encoder.call_args.args[1], ['gamma'])


if __name__ == '__main__':
    unittest.main()
