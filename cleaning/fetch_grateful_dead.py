"""
fetch_grateful_dead.py
Fetches Grateful Dead concerts from Internet Archive (1965-1979).
- One recording per date (best quality: sbd > mtx > aud)
- Only VBR MP3 tracks over 5 minutes
- Outputs data/genre/grateful-dead.json
"""

import json, urllib.request, urllib.error, time, os, sys

OUT_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'genre', 'grateful-dead.json')
MIN_DURATION = 300  # 5 minutes

def fetch(url, retries=3):
    for i in range(retries):
        try:
            return json.loads(urllib.request.urlopen(url, timeout=15).read())
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
            else:
                raise e

def parse_duration(s):
    try:
        p = s.split(':')
        if len(p) == 2: return int(p[0]) * 60 + int(p[1])
        if len(p) == 3: return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except: pass
    return 0

def quality_rank(identifier):
    id_lower = identifier.lower()
    if '.sbd.' in id_lower or id_lower.startswith('gd') and 'sbd' in id_lower: return 0
    if '.mtx.' in id_lower: return 1
    return 2  # aud or unknown

# ── Step 1: Fetch all items 1965-1979 ────────────────────

print('Fetching all items 1965-1979...')
all_items = []
page = 1
while True:
    url = (
        'https://archive.org/advancedsearch.php'
        '?q=collection:GratefulDead+AND+date:[1965-01-01T00:00:00Z+TO+1979-12-31T23:59:59Z]'
        '&fl=identifier,date&rows=500'
        f'&page={page}&output=json'
    )
    data = fetch(url)
    docs = data['response']['docs']
    if not docs:
        break
    all_items.extend(docs)
    print(f'  page {page}: {len(all_items)} items')
    page += 1

print(f'Total items: {len(all_items)}')

# ── Step 2: Pick best recording per date ─────────────────

by_date = {}
for item in all_items:
    date = item.get('date', '')[:10]
    if not date:
        continue
    id = item['identifier']
    rank = quality_rank(id)
    if date not in by_date or rank < by_date[date][1]:
        by_date[date] = (id, rank)

best = [(date, id) for date, (id, rank) in sorted(by_date.items())]
print(f'Unique dates: {len(best)}')

# ── Step 3: Fetch tracks for each concert ────────────────

tracks = []
errors = 0

for i, (date, identifier) in enumerate(best):
    try:
        meta = fetch(f'https://archive.org/metadata/{identifier}')
        files = meta.get('files', [])
        m = meta.get('metadata', {})
        concert_title = m.get('title', f'Grateful Dead Live {date}')

        mp3s = [
            f for f in files
            if f.get('format') == 'VBR MP3'
            and parse_duration(f.get('length', '0')) >= MIN_DURATION
        ]

        for f in mp3s:
            track_title = f.get('title') or f['name'].replace('.mp3', '').replace('_', ' ')
            duration = parse_duration(f.get('length', '0'))
            tracks.append({
                'track_id':        f'TRK-GD-{identifier}-{f["name"]}',
                'title':           track_title,
                'artist_name':     'Grateful Dead',
                'album_title':     concert_title,
                'duration_sec':    duration,
                'cover_art_url':   None,
                'stream_url':      f'https://archive.org/download/{identifier}/{f["name"]}',
                'source_platform': 'internet_archive',
                'license_type':    'https://creativecommons.org/licenses/by-sa/4.0/',
                'is_downloadable': True,
                'attribution_text': f'"{track_title}" by Grateful Dead — {concert_title} — archive.org/details/{identifier}',
            })

        print(f'[{i+1}/{len(best)}] {date} {identifier}: {len(mp3s)} tracks')
        time.sleep(0.1)  # be polite to IA

    except Exception as e:
        errors += 1
        print(f'[{i+1}/{len(best)}] ERROR {identifier}: {e}')

# ── Step 4: Write output ──────────────────────────────────

os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(tracks, f, ensure_ascii=False)

size_mb = os.path.getsize(OUT_FILE) / (1024 * 1024)
print(f'\nDone. {len(tracks):,} tracks written to {OUT_FILE}')
print(f'File size: {size_mb:.1f} MB')
print(f'Errors: {errors}')
