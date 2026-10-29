import sys
sys.path.insert(0, 'backend')
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

from ingestion.ia_adapter import IAAdapter
from ingestion.normalizer import normalize
from ingestion.deduplicator import is_duplicate
from db.dynamo_client import put_track

adapter = IAAdapter()
print('Fetching page 0 from Internet Archive...')
raw_records = adapter.fetch(1)
print(f'Fetched {len(raw_records)} raw records\n')

written = 0
skipped_no_mp3 = 0
skipped_invalid = 0
skipped_duplicate = 0

for raw in raw_records:
    # Step 1: adapter normalize (source-specific mapping)
    adapted = adapter.normalize(raw)
    if not adapted:
        skipped_no_mp3 += 1
        continue

    # Step 2: schema normalize (validation + coercion)
    validated = normalize(adapted)
    if not validated:
        skipped_invalid += 1
        continue

    # Step 3: deduplication
    if is_duplicate(validated["track_id"], validated.get("audio_hash_md5")):
        skipped_duplicate += 1
        continue

    # Step 4: write to DynamoDB
    if put_track(validated):
        written += 1
        title = validated["title"].encode("ascii", "replace").decode()
        artist = validated["artist_name"].encode("ascii", "replace").decode()
        print(f'  + {validated["track_id"]} | {title} | {artist}')

print(f'\nResults:')
print(f'  Written:           {written}')
print(f'  Skipped (no MP3):  {skipped_no_mp3}')
print(f'  Skipped (invalid): {skipped_invalid}')
print(f'  Skipped (dedup):   {skipped_duplicate}')
