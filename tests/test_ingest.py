import sys
sys.path.insert(0, 'backend')
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

from ingestion.ia_adapter import IAAdapter
from ingestion.normalizer import normalize
from ingestion.deduplicator import is_duplicate
from db.dynamo_client import put_track

adapter = IAAdapter()

total_written = 0
total_skipped_no_mp3 = 0
total_skipped_invalid = 0
total_skipped_duplicate = 0
total_skipped_not_public = 0

PAGES = 50  # 50 pages x 50 records = 2,500 candidates

for page in range(PAGES):
    print(f'\n--- Page {page} ---')
    raw_records = adapter.fetch(page)
    if not raw_records:
        print('No more records.')
        break

    for raw in raw_records:
        adapted = adapter.normalize(raw)
        if not adapted:
            total_skipped_no_mp3 += 1
            continue

        validated = normalize(adapted)
        if not validated:
            total_skipped_invalid += 1
            continue

        if is_duplicate(validated['track_id'], validated.get('audio_hash_md5')):
            total_skipped_duplicate += 1
            continue

        if put_track(validated):
            total_written += 1
            title  = validated['title'].encode('ascii', 'replace').decode()
            artist = validated['artist_name'].encode('ascii', 'replace').decode()
            ct     = validated.get('content_type', 'other')
            genre  = validated['genre'].encode('ascii', 'replace').decode()
            print(f'  + [{ct}] {title} | {artist} | {genre}')

print(f'\n=== Final Results ===')
print(f'  Written:           {total_written}')
print(f'  Skipped (no MP3 / not public): {total_skipped_no_mp3}')
print(f'  Skipped (invalid): {total_skipped_invalid}')
print(f'  Skipped (dedup):   {total_skipped_duplicate}')
