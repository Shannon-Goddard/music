"""
Probe Openverse API for audio sources, data shape, and CORS on stream URLs.
Run: python scripts/probe_openverse.py

Openverse aggregates:
  - Jamendo       644k tracks
  - Wikimedia     3.98M audio files
  - Freesound     591k (sound effects, less useful)

Docs: https://api.openverse.org/v1/
"""
import requests, json, time

BASE    = 'https://api.openverse.org/v1'
HEADERS = {'Accept': 'application/json', 'User-Agent': 'MusicMetaIndex/1.0'}

s = requests.Session()
s.headers.update(HEADERS)

def get(path, params=None, timeout=20):
    try:
        r = s.get(f'{BASE}{path}', params=params, timeout=timeout)
        print(f'  {r.status_code} {path}')
        return r
    except requests.RequestException as e:
        print(f'  ERR {path}: {e}')
        return None

# ── 1. Stats ──────────────────────────────────────────────
print('\n=== Sources ===')
r = get('/audio/stats/')
if r and r.ok:
    for src in r.json():
        print(f"  {src['source_name']:20} {src['media_count']:>10,} tracks")

time.sleep(1)

# ── 2. Sample search — Jamendo source ────────────────────
print('\n=== Sample: Jamendo jazz ===')
r = get('/audio/', {'q': 'jazz', 'source': 'jamendo', 'page_size': 2, 'license_type': 'commercial'})
if r and r.ok:
    data = r.json()
    print(f'  total results: {data.get("result_count")}')
    for t in data.get('results', []):
        print(f'  title:    {t.get("title")}')
        print(f'  creator:  {t.get("creator")}')
        print(f'  license:  {t.get("license")}')
        print(f'  url:      {t.get("url")}')
        print(f'  audio:    {t.get("audio_url") or t.get("url")}')
        print(f'  duration: {t.get("duration")}')
        print(f'  tags:     {[tg.get("name") for tg in t.get("tags", [])[:5]]}')
        print(f'  source:   {t.get("source")}')
        print()

time.sleep(1)

# ── 3. Sample search — Wikimedia source ──────────────────
print('\n=== Sample: Wikimedia classical ===')
r = get('/audio/', {'q': 'classical', 'source': 'wikimedia_audio', 'page_size': 2})
if r and r.ok:
    data = r.json()
    print(f'  total results: {data.get("result_count")}')
    for t in data.get('results', []):
        print(f'  title:    {t.get("title")}')
        print(f'  creator:  {t.get("creator")}')
        print(f'  license:  {t.get("license")}')
        print(f'  audio:    {t.get("audio_url") or t.get("url")}')
        print(f'  duration: {t.get("duration")}')
        print()

time.sleep(1)

# ── 4. CORS check on a stream URL ────────────────────────
print('\n=== CORS check on stream URLs ===')
r = get('/audio/', {'q': 'music', 'source': 'jamendo', 'page_size': 1})
if r and r.ok:
    results = r.json().get('results', [])
    if results:
        audio_url = results[0].get('audio_url') or results[0].get('url')
        print(f'  checking: {audio_url}')
        try:
            h = requests.head(audio_url, timeout=10, allow_redirects=True)
            cors = h.headers.get('Access-Control-Allow-Origin', 'MISSING')
            ct   = h.headers.get('Content-Type', '')
            print(f'  status: {h.status_code}')
            print(f'  CORS:   {cors}')
            print(f'  type:   {ct}')
        except Exception as e:
            print(f'  ERR: {e}')

# ── 5. Full field list from one record ───────────────────
print('\n=== Full field list (one record) ===')
r = get('/audio/', {'q': 'jazz', 'page_size': 1})
if r and r.ok:
    results = r.json().get('results', [])
    if results:
        print(json.dumps(results[0], indent=2))
