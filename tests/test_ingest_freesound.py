"""
Ingest Freesound audio into DynamoDB.

Usage:
  python -u tests/test_ingest_freesound.py                      # all tags
  python -u tests/test_ingest_freesound.py --tag jazz           # one tag
  python -u tests/test_ingest_freesound.py --tag jazz --limit 200
  python -u tests/test_ingest_freesound.py --dry-run            # no DB writes
"""
import sys, os, argparse, logging, time
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import boto3
from botocore.exceptions import ClientError
from ingestion.freesound_adapter import FreesoundAdapter, FREESOUND_TAGS
import ingestion.deduplicator as deduplicator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TABLE  = os.environ.get('DYNAMODB_TABLE', 'music-tracks')
REGION = os.environ.get('AWS_REGION', 'us-east-1')


def _get_table():
    return boto3.resource('dynamodb', region_name=REGION).Table(TABLE)


def ingest_tag(tag: str, limit: int, dry_run: bool) -> tuple[int, int, int]:
    """Returns (written, dupes, skipped)."""
    adapter   = FreesoundAdapter(tag=tag)
    seen_ids  = set()
    table     = None if dry_run else _get_table()
    written   = dupes = skipped = 0

    logger.info('-- Tag: %s', tag)

    while adapter.has_more():
        raws = adapter.fetch()
        if not raws:
            break

        for raw in raws:
            record = adapter.normalize(raw)
            if record is None:
                skipped += 1
                continue

            tid = record['track_id']
            if tid in seen_ids:
                dupes += 1
                continue
            if not dry_run and deduplicator.is_duplicate(tid, None):
                dupes += 1
                seen_ids.add(tid)
                continue
            seen_ids.add(tid)

            if dry_run:
                logger.info('DRY-RUN: %s | %s | %s | %.0fs',
                            tid, record['title'][:40], record['artist_name'][:25],
                            float(record.get('duration_sec', 0)))
                written += 1
            else:
                try:
                    table.put_item(Item=record)
                    written += 1
                except ClientError as e:
                    logger.error('DynamoDB error: %s', e)
                    skipped += 1

            if limit and written >= limit:
                logger.info('Reached limit %d', limit)
                return written, dupes, skipped

        logger.info('  progress: written=%d  dupes=%d  skipped=%d', written, dupes, skipped)

    return written, dupes, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',        default='', help='Single tag to ingest (default: all)')
    parser.add_argument('--start-tag',  default='', help='Resume from this tag (skips earlier tags)')
    parser.add_argument('--limit',      type=int, default=0, help='Max records per tag (0=unlimited)')
    parser.add_argument('--dry-run',    action='store_true')
    args = parser.parse_args()

    if args.tag:
        tags = [args.tag]
    elif args.start_tag:
        try:
            idx = FREESOUND_TAGS.index(args.start_tag)
            tags = FREESOUND_TAGS[idx:]
            logger.info('Resuming from tag: %s (%d tags remaining)', args.start_tag, len(tags))
        except ValueError:
            logger.error('Unknown start-tag: %s', args.start_tag)
            sys.exit(1)
    else:
        tags = FREESOUND_TAGS

    logger.info('=== Freesound ingest start ===')
    logger.info('tags=%s  limit=%s  dry_run=%s', tags, args.limit or 'unlimited', args.dry_run)

    total_written = total_dupes = total_skipped = 0

    for tag in tags:
        w, d, s = ingest_tag(tag, args.limit, args.dry_run)
        total_written  += w
        total_dupes    += d
        total_skipped  += s
        logger.info('Tag %s done: written=%d  dupes=%d  skipped=%d', tag, w, d, s)
        time.sleep(2)  # pause between tags

    logger.info('=== DONE: written=%d  dupes=%d  skipped=%d ===', total_written, total_dupes, total_skipped)


if __name__ == '__main__':
    main()
