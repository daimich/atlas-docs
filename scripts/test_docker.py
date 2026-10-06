"""Exercise the built image over HTTP, including a named-volume restart."""
import base64
import json
import subprocess
import sys
import time
import urllib.request
import uuid

image = sys.argv[1] if len(sys.argv) > 1 else 'atlas-docs:test'
name = 'atlas-test-' + uuid.uuid4().hex[:12]
volume = name + '-data'
base = 'http://127.0.0.1:8080/api/'


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout


def api(path, payload=None):
    request = urllib.request.Request(base + path, headers={'Content-Type': 'application/json'},
        data=None if payload is None else json.dumps(payload).encode())
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def start():
    docker('run', '-d', '--name', name, '-p', '127.0.0.1:8080:8080', '-v', volume + ':/data', image)
    for _ in range(60):
        try:
            if api('health')['status'] == 'ok':
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError('Container did not become healthy: ' + docker('logs', name))


try:
    start()
    assert api('status')['pdf_available']
    assert api('ask', {'question': 'payment terms'})['claims']
    document = api('ingest', {'name': 'durable.md', 'base64': base64.b64encode(b'Durabilitytest survives container replacement.').decode()})
    docker('rm', '-f', name)
    start()
    assert api('search', {'question': 'durabilitytest'})['hits'][0]['name'] == 'durable.md'
    api('delete', {'id': document['id']})
    assert not api('search', {'question': 'durabilitytest'})['hits']
    print('PASS: image startup, PDF dependency, API, persistence across container replacement, deletion')
finally:
    subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)
