import sys
sys.path.insert(0, 'backend')
from ingestion.ia_adapter import IAAdapter, IA_COLLECTIONS
from ingestion.normalizer import normalize
import requests

adapter = IAAdapter()

# --- georgeblood: check what the raw query returns ---
print('=== georgeblood query ===')
print('Query:', IA_COLLECTIONS['georgeblood'])
import requests as req
resp = req.get('https://archive.org/advancedsearch.php', params={
    'q': IA_COLLECTIONS['georgeblood'],
    'fl[]': ['identifier','title','licenseurl'],
    'rows': 3, 'page': 1, 'output': 'json'
}, timeout=15)
import json
d = resp.json()
print('numFound:', d['response']['numFound'])
for r in d['response']['docs']:
    print(' ', r)
sys.stdout.flush()

# --- opensource_audio: why does normalize fail? ---
print('\n=== opensource_audio first record ===')
records = adapter.fetch(0, 'opensource_audio')
raw = records[0]
print('raw keys:', list(raw.keys()))
print('licenseurl:', raw.get('licenseurl'))
adapted = adapter.normalize(raw, 'opensource_audio')
print('adapted:', adapted)
sys.stdout.flush()

# --- audio_bookspoetry: same ---
print('\n=== audio_bookspoetry first record ===')
records2 = adapter.fetch(0, 'audio_bookspoetry')
raw2 = records2[0]
print('licenseurl:', raw2.get('licenseurl'))
adapted2 = adapter.normalize(raw2, 'audio_bookspoetry')
print('adapted:', adapted2)
sys.stdout.flush()
