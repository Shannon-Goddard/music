"""
Ingest Wikimedia Commons audio into DynamoDB.

Usage:
  python -u tests/test_ingest_wikimedia.py                        # all genres
  python -u tests/test_ingest_wikimedia.py --genre classical      # one genre
  python -u tests/test_ingest_wikimedia.py --genre jazz --limit 200
  python -u tests/test_ingest_wikimedia.py --dry-run              # no DB writes
"""
import sys, os, argparse, logging, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import boto3
from botocore.exceptions import ClientError
from ingestion.wikimedia_adapter import WikimediaAdapter, GENRE_CATEGORIES
import ingestion.deduplicator as deduplicator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TABLE   = os.environ.get('DYNAMODB_TABLE', 'music-tracks')
REGION  = os.environ.get('AWS_REGION', 'us-east-1')


def _get_table():
    return boto3.resource('dynamodb', region_name=REGION).Table(TABLE)


def ingest_genre(genre: str, limit: int, dry_run: bool) -> tuple[int, int, int]:
    """Returns (written, dupes, skipped)."""
    adapter = WikimediaAdapter(genre=genre)
    seen_urls: set[str] = set()  # in-memory dedup by stream URL
    table   = None if dry_run else _get_table()

    written = dupes = skipped = 0

    logger.info('-- Genre: %s  category: %s', genre, adapter.category)

    while adapter.has_more():
        raw_pages = adapter.fetch(0)
        if not raw_pages:
            break

        for raw in raw_pages:
            record = adapter.normalize(raw)
            if record is None:
                skipped += 1
                continue

            # Dedup: check in-memory first, then DB
            url = record['stream_url']
            if url in seen_urls:
                dupes += 1
                continue
            if not dry_run and deduplicator.is_duplicate(record['track_id'], None):
                dupes += 1
                seen_urls.add(url)
                continue
            seen_urls.add(url)

            if dry_run:
                logger.info('DRY-RUN: %s | %s | %s', record['track_id'], record['title'][:40], record['artist_name'][:30])
                written += 1
            else:
                try:
                    table.put_item(Item=record)
                    written += 1
                except ClientError as e:
                    logger.error('DynamoDB error: %s', e)
                    skipped += 1

            if limit and written >= limit:
                logger.info('Reached limit of %d', limit)
                return written, dupes, skipped

        logger.info('  progress: written=%d  dupes=%d  skipped=%d', written, dupes, skipped)

        if not adapter.has_more():
            break

    return written, dupes, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--genre',   default='', help='Single genre to ingest (default: all)')
    parser.add_argument('--limit',   type=int, default=0, help='Max records per genre (0=unlimited)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    genres = [args.genre] if args.genre else list(GENRE_CATEGORIES.keys())

    logger.info('=== Wikimedia Commons ingest start ===')
    logger.info('genres=%s  limit=%s  dry_run=%s', genres, args.limit or 'unlimited', args.dry_run)

    total_written = total_dupes = total_skipped = 0

    for genre in genres:
        w, d, s = ingest_genre(genre, args.limit, args.dry_run)
        total_written  += w
        total_dupes    += d
        total_skipped  += s
        logger.info('Genre %s done: written=%d  dupes=%d  skipped=%d', genre, w, d, s)
        time.sleep(1)

    logger.info('=== DONE: written=%d  dupes=%d  skipped=%d ===', total_written, total_dupes, total_skipped)


if __name__ == '__main__':
    main()
