"""
Full ingest from targeted IA collections: netlabels + 78rpm.
Run with: python tests/test_ingest.py

Wipes existing data first, then ingests clean.
"""
import sys
sys.path.insert(0, 'backend')
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

import boto3
from ingestion.ia_adapter import IAAdapter, IA_COLLECTIONS
from ingestion.normalizer import normalize
from ingestion.deduplicator import is_duplicate
from db.dynamo_client import put_track

# ── Wipe existing table ───────────────────────────────────────────────

def wipe_table():
    table = boto3.resource('dynamodb', region_name='us-east-1').Table('music-tracks')
    print('Scanning for existing records...')
    deleted = 0
    scan_kwargs = {}
    while True:
        resp = table.scan(ProjectionExpression='track_id', **scan_kwargs)
        with table.batch_writer() as batch:
            for item in resp.get('Items', []):
                batch.delete_item(Key={'track_id': item['track_id']})
                deleted += 1
        last = resp.get('LastEvaluatedKey')
        if not last:
            break
        scan_kwargs['ExclusiveStartKey'] = last
    print(f'Wiped {deleted} existing records.\n')

# ── Ingest one collection ─────────────────────────────────────────────

def ingest_collection(adapter, collection, pages):
    written = skipped_stream = skipped_dedup = 0
    print(f'\n{"="*50}')
    print(f'Collection: {collection}  ({pages} pages x 50 = {pages*50} candidates)')
    print(f'{"="*50}')

    for page in range(pages):
        raw_records = adapter.fetch(page, collection)
        if not raw_records:
            print(f'  [page {page}] no more records')
            break

        for raw in raw_records:
            adapted = adapter.normalize(raw, collection)
            if not adapted:
                skipped_stream += 1
                continue

            validated = normalize(adapted)
            if not validated:
                skipped_stream += 1
                continue

            if is_duplicate(validated['track_id'], validated.get('audio_hash_md5')):
                skipped_dedup += 1
                continue

            if put_track(validated):
                written += 1
                title  = validated['title'].encode('ascii', 'replace').decode()
                artist = validated['artist_name'].encode('ascii', 'replace').decode()
                ct     = validated.get('content_type', 'other')
                print(f'  + [{ct}] {title} | {artist}')

    print(f'\n  {collection}: written={written}, skipped={skipped_stream}, dedup={skipped_dedup}')
    return written

# ── Main ──────────────────────────────────────────────────────────────

wipe_table()

adapter = IAAdapter()
total = 0

# netlabels: modern CC music releases — run more pages, very dense
total += ingest_collection(adapter, 'netlabels', pages=100)

# 78rpm: pre-1930s jazz/blues/classical — public domain
total += ingest_collection(adapter, '78rpm', pages=100)

print(f'\n{"="*50}')
print(f'TOTAL WRITTEN: {total}')
print(f'{"="*50}')
