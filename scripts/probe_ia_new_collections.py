import sys
sys.path.insert(0, 'backend')
from ingestion.ia_adapter import IAAdapter
from ingestion.normalizer import normalize

adapter = IAAdapter()
cols = ['opensource_audio', 'audio_music', 'georgeblood', 'audio_bookspoetry', 'librivoxaudio']

for col in cols:
    records = adapter.fetch(0, col)
    if not records:
        print(f'{col}: 0 records returned')
        sys.stdout.flush()
        continue
    adapted = adapter.normalize(records[0], col)
    validated = normalize(adapted) if adapted else None
    status = 'OK' if validated else 'FAILED'
    ct = (validated or {}).get('content_type', '?')
    title = (validated or {}).get('title', '?')[:50]
    print(f'{col}: {len(records)} fetched | first -> [{ct}] {title} | {status}')
    sys.stdout.flush()
