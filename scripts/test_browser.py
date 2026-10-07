"""Browser acceptance: python -m pip install playwright; playwright install chromium."""
from pathlib import Path
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas.service import Service
from atlas.web import make_server


def main():
    with tempfile.TemporaryDirectory() as folder:
        service = Service(Path(folder) / 'index.sqlite3')
        server = make_server(service, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('#count')).to_have_text('0 documents')
                page.locator('#upload').set_input_files({'name': 'notice.md', 'mimeType': 'text/markdown',
                    'buffer': b'Termination requires thirty days of written notice.'})
                expect(page.locator('#count')).to_have_text('1 documents')
                expect(page.locator('#upload')).to_be_enabled()
                page.locator('#query').fill('How much notice is required for termination?')
                page.locator('#submit').click()
                expect(page.locator('#results blockquote')).to_contain_text('thirty days')
                expect(page.locator('#results .citation')).to_contain_text('notice.md')
                # Exercise presentation of a valid abstention using the real retrieved evidence.
                def abstain(route):
                    response = route.fetch()
                    payload = dict(response.json(), mode='ollama', abstained=True, claims=[])
                    route.fulfill(response=response, json=payload)
                page.route('**/api/ask', abstain)
                page.locator('#submit').click()
                expect(page.locator('#mode')).to_have_text('Source evidence · model abstained')
                expect(page.locator('#results blockquote')).to_contain_text('thirty days')
                page.unroute('**/api/ask', abstain)
                page.reload()
                expect(page.locator('#count')).to_have_text('1 documents')
                page.get_by_title('Delete notice.md').click()
                expect(page.locator('#count')).to_have_text('0 documents')
                page.locator('#query').fill('termination notice')
                page.locator('#submit').click()
                expect(page.locator('#results')).to_contain_text('No matching evidence')
                page.locator('#upload').set_input_files({'name': 'bad.exe', 'mimeType': 'application/octet-stream', 'buffer': b'unsupported'})
                expect(page.locator('#status')).to_contain_text('Supported formats')
                expect(page.locator('#upload')).to_be_enabled()
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
    print('PASS: empty state, upload, cited answer, abstention evidence, reload, deletion, validation, no browser errors')


if __name__ == '__main__':
    main()
