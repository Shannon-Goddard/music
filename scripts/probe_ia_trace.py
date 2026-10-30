import sys, logging
sys.path.insert(0, 'backend')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
from ingestion.ia_adapter import IAAdapter
import requests

adapter = IAAdapter()

# Get first record from opensource_audio
records = adapter.fetch(0, 'opensource_audio')
raw = records[0]
identifier = raw['identifier']
print('identifier:', identifier)
sys.stdout.flush()

# Step through normalize manually
license_url = raw.get('licenseurl', '')
print('license_url:', license_url)
sys.stdout.flush()

meta = adapter._fetch_metadata(identifier)
print('meta keys:', list(meta.keys()) if meta else None)
sys.stdout.flush()

if meta:
    files = meta.get('files', [])
    mp3s = [f for f in files if f.get('name','').lower().endswith('.mp3')]
    print(f'total files: {len(files)}, mp3s: {len(mp3s)}')
    if mp3s:
        print('first mp3:', mp3s[0].get('name'))
        stream_url = f"https://archive.org/download/{identifier}/{mp3s[0]['name']}"
        print('stream_url:', stream_url)
        sys.stdout.flush()
        # Check streamability
        try:
            r = requests.head(stream_url, timeout=10, allow_redirects=True)
            print('HEAD status:', r.status_code)
        except Exception as e:
            print('HEAD error:', e)
    else:
        print('no mp3s found — file names:')
        for f in files[:10]:
            print(' ', f.get('name'), f.get('format'))
sys.stdout.flush()

# Try audio_bookspoetry too
print('\n--- audio_bookspoetry ---')
records2 = adapter.fetch(0, 'audio_bookspoetry')
raw2 = records2[0]
identifier2 = raw2['identifier']
print('identifier:', identifier2)
meta2 = adapter._fetch_metadata(identifier2)
if meta2:
    files2 = meta2.get('files', [])
    mp3s2 = [f for f in files2 if f.get('name','').lower().endswith('.mp3')]
    print(f'total files: {len(files2)}, mp3s: {len(mp3s2)}')
    if mp3s2:
        stream_url2 = f"https://archive.org/download/{identifier2}/{mp3s2[0]['name']}"
        r2 = requests.head(stream_url2, timeout=10, allow_redirects=True)
        print('HEAD status:', r2.status_code)
    else:
        print('no mp3s — formats:', list({f.get('format') for f in files2}))
sys.stdout.flush()
