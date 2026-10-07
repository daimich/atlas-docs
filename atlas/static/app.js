const $ = (id) => document.getElementById(id);
const node = (tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if (cls) el.className = cls; return el; };
async function api(path, body) {
  const response = await fetch('/api/' + path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function status(message) { $('status').textContent = message; }
async function refresh() {
  const docs = await api('documents'); $('inventory').replaceChildren();
  $('count').textContent = docs.length + ' documents';
  for (const doc of docs) {
    const row = node('div', '', 'doc');
    const info = node('div', '', 'doc-info');
    info.append(node('strong', doc.name), node('small', doc.pages + ' pages · ' + doc.chunks + ' passages'));
    const remove = node('button', '×', 'remove'); remove.title = 'Delete ' + doc.name;
    remove.addEventListener('click', async () => {
      try { await api('delete', {id: doc.id}); await refresh(); $('results').replaceChildren(); status('Document removed.'); }
      catch (error) { status(error.message); }
    });
    row.append(info, remove); $('inventory').append(row);
  }
  if (!docs.length) $('inventory').append(node('p', 'Your workspace is empty. Upload a document to begin.', 'muted'));
}
$('upload').addEventListener('change', async (event) => {
  const files = Array.from(event.target.files); $('upload').disabled = true;
  try {
    for (const file of files) {
      if (file.size > 15 * 1024 * 1024) throw new Error(file.name + ' exceeds 15 MiB');
      status('Indexing ' + file.name + '…');
      const encoded = await new Promise((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = () => reject(new Error('Could not read file')); reader.readAsDataURL(file);
      });
      await api('ingest', {name: file.name, base64: encoded});
    }
    await refresh(); status('Documents indexed. Ready to search.');
  } catch (error) { status(error.message); }
  finally { $('upload').value = ''; $('upload').disabled = false; await refresh().catch(error => status(error.message)); }
});
$('query-form').addEventListener('submit', async (event) => {
  event.preventDefault(); $('submit').disabled = true; status('Searching the evidence…');
  try {
    const result = await api('ask', {question: $('query').value, k: 5}); $('results').replaceChildren();
    const showEvidence = result.abstained && result.evidence.length > 0;
    $('mode').textContent = showEvidence ? 'Source evidence · model abstained' : (result.mode === 'ollama' ? 'Generated answer · quotes checked' : 'Evidence excerpts');
    if (result.abstained) $('results').append(node('div', showEvidence ? 'The model could not support an answer. Review the retrieved passages below.' : 'No matching evidence was found. Try a more specific question or add documents.', 'empty'));
    const claims = showEvidence ? result.evidence.map(source => ({...source, quote: source.text})) : result.claims;
    claims.forEach((claim, index) => {
      const card = node('article', '', 'card');
      card.append(node('div', '[' + (index + 1) + '] ' + claim.name + ' · page ' + claim.page, 'citation'));
      if (result.mode === 'ollama' && !showEvidence) card.append(node('p', claim.text, 'claim'));
      card.append(node('blockquote', claim.quote)); $('results').append(card);
    });
    status(result.retrieval + ' · retrieval ' + result.latency_ms + ' ms');
  } catch (error) { status(error.message); }
  finally { $('submit').disabled = false; }
});
document.querySelectorAll('[data-query]').forEach(button => button.addEventListener('click', () => {
  $('query').value = button.dataset.query; $('query').focus();
}));
refresh().catch(error => status(error.message));

api('status').then(meta => { $('model-info').textContent = meta.retrieval + ' · ' + (meta.ollama_model || 'source excerpts') + (meta.pdf_available ? ' · PDF ready' : ' · PDF: install the pdf extra'); }).catch(error => status(error.message));
