"""
Backfill content_type for tracks sitting as 'other'.

Rules (deterministic, no API calls needed):
  ia_collection=georgeblood   → music
  ia_collection=librivoxaudio → audiobook
  ia_collection=audio_bookspoetry → audiobook  (most are readings)
  source_platform=wikimedia   → music           (already set, safety net)

Usage:
  python -u tests/backfill_content_type.py            # live run
  python -u tests/backfill_content_type.py --dry-run  # preview only
  python -u tests/backfill_content_type.py --limit 500
"""
import sys, os, argparse, logging
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TABLE  = os.environ.get('DYNAMODB_TABLE', 'music-tracks')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

# collection → content_type override
COLLECTION_RULES = {
    'georgeblood':       'music',
    'librivoxaudio':     'audiobook',
    'audio_bookspoetry': 'audiobook',
}


def _resolve(item: dict) -> str | None:
    """Return the correct content_type, or None if we can't determine it."""
    collection = item.get('ia_collection', '')
    if collection in COLLECTION_RULES:
        return COLLECTION_RULES[collection]
    if item.get('source_platform') == 'wikimedia':
        return 'music'
    return None


def run(dry_run: bool, limit: int):
    table = boto3.resource('dynamodb', region_name=REGION).Table(TABLE)

    updated = skipped = errors = 0
    last_key = None

    scan_kwargs = {
        'FilterExpression': Attr('content_type').eq('other'),
        'ProjectionExpression': 'track_id, ia_collection, source_platform',
    }

    logger.info('=== content_type backfill start  dry_run=%s ===', dry_run)

    while True:
        if last_key:
            scan_kwargs['ExclusiveStartKey'] = last_key

        resp     = table.scan(**scan_kwargs)
        items    = resp.get('Items', [])
        last_key = resp.get('LastEvaluatedKey')

        for item in items:
            new_ct = _resolve(item)
            if new_ct is None:
                skipped += 1
                continue

            tid = item['track_id']
            if dry_run:
                logger.info('DRY-RUN  %s  →  %s', tid, new_ct)
            else:
                try:
                    table.update_item(
                        Key={'track_id': tid},
                        UpdateExpression='SET content_type = :ct',
                        ExpressionAttributeValues={':ct': new_ct},
                    )
                except ClientError as e:
                    logger.error('update failed %s: %s', tid, e)
                    errors += 1
                    continue

            updated += 1
            if limit and updated >= limit:
                logger.info('Reached limit %d', limit)
                logger.info('=== DONE  updated=%d  skipped=%d  errors=%d ===', updated, skipped, errors)
                return

        logger.info('  progress: updated=%d  skipped=%d  errors=%d', updated, skipped, errors)

        if not last_key:
            break

    logger.info('=== DONE  updated=%d  skipped=%d  errors=%d ===', updated, skipped, errors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    run(args.dry_run, args.limit)


if __name__ == '__main__':
    main()
