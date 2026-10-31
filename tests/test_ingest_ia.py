"""
Ingest IA collections into DynamoDB — additive, threaded, resumable.

Usage:
  python tests/test_ingest_ia.py <collection> [--start-page N]

Examples:
  python tests/test_ingest_ia.py opensource_audio
  python tests/test_ingest_ia.py audio_music --start-page 40
  python tests/test_ingest_ia.py georgeblood

Collections: netlabels, 78rpm, opensource_audio, audio_music,
             georgeblood, audio_bookspoetry, librivoxaudio
"""
import sys
import logging
sys.path.insert(0, 'backend')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

import boto3
from ingestion.ia_adapter import IAAdapter, IA_COLLECTIONS
from ingestion.normalizer import normalize
from ingestion.deduplicator import is_duplicate
from db.dynamo_client import put_track

# No hard cap — runs until 3 consecutive empty pages (same as Jamendo)
PAGES = {k: 999_999 for k in IA_COLLECTIONS}


def ingest_collection(adapter, collection, max_pages, start_page=0):
    written = skipped = deduped = 0
    consecutive_empty = 0

    print(f'\n{"="*55}')
    print(f'  {collection}')
    print(f'  pages {start_page}–{start_page + max_pages - 1}  (50 items/page, 10 workers)')
    print(f'{"="*55}')
    sys.stdout.flush()

    for page in range(start_page, start_page + max_pages):
        raw_records = adapter.fetch(page, collection)

        if not raw_records:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                print(f'  [page {page}] 3 empty pages — done')
                break
            continue
        consecutive_empty = 0

        # Parallel metadata + HEAD checks for the whole page
        adapted_batch = adapter.normalize_batch(raw_records, collection)

        for adapted in adapted_batch:
            validated = normalize(adapted)
            if not validated:
                skipped += 1
                continue

            if is_duplicate(validated['track_id'], validated.get('audio_hash_md5')):
                deduped += 1
                continue

            if put_track(validated):
                written += 1

        print(f'  page {page:>4} | +{len(adapted_batch):>3} valid | '
              f'written={written}  skipped={skipped}  deduped={deduped}')
        sys.stdout.flush()

    print(f'\n  DONE {collection}: written={written}  skipped={skipped}  deduped={deduped}')
    return written


# ── Argument parsing ──────────────────────────────────────────────────

args = sys.argv[1:]

if not args or args[0] not in IA_COLLECTIONS:
    print(__doc__)
    print(f'Available collections: {list(IA_COLLECTIONS.keys())}')
    sys.exit(1)

collection = args[0]
start_page = 0
if '--start-page' in args:
    idx = args.index('--start-page')
    start_page = int(args[idx + 1])

adapter  = IAAdapter()
max_pages = PAGES[collection]
ingest_collection(adapter, collection, max_pages, start_page)
