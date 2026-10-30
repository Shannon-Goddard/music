"""
Backfill duration_sec for Internet Archive tracks that are missing it.

Hits archive.org/metadata/{identifier} for each track, picks the same
audio file the ingestor would have chosen (best MP3 → WAV → M4A),
reads the 'length' field, and writes it back to DynamoDB.

Rate: ~1 req/s to be polite to IA. ~25k tracks ≈ 7 hours unattended.
Run overnight or in a screen/tmux session.

Usage:
  python -u tests/backfill_duration.py            # live run
  python -u tests/backfill_duration.py --dry-run  # preview, no writes
  python -u tests/backfill_duration.py --limit 200
  python -u tests/backfill_duration.py --workers 3   # parallel (be careful)
"""
import sys, os, argparse, logging, time
from decimal import Decimal, InvalidOperation
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import boto3
import requests
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TABLE    = os.environ.get('DYNAMODB_TABLE', 'music-tracks')
REGION   = os.environ.get('AWS_REGION', 'us-east-1')
IA_META  = 'https://archive.org/metadata'
RATE_SEC = 1.0   # seconds between IA requests (single-worker default)


def _to_decimal(value) -> Decimal | None:
    try:
        return Decimal(str(float(value))).quantize(Decimal('0.01'))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _pick_audio(files: list[dict]) -> dict | None:
    def ext(f): return f.get('name', '').lower()
    mp3s = sorted([f for f in files if ext(f).endswith('.mp3')],
                  key=lambda f: float(f.get('bitrate') or 0), reverse=True)
    if mp3s: return mp3s[0]
    wavs = [f for f in files if ext(f).endswith('.wav')]
    if wavs: return wavs[0]
    m4as = [f for f in files if ext(f).endswith(('.m4a', '.mp4'))]
    if m4as: return m4as[0]
    return None


def _fetch_duration(identifier: str) -> Decimal | None:
    try:
        r = requests.get(f'{IA_META}/{identifier}', timeout=30)
        r.raise_for_status()
        audio = _pick_audio(r.json().get('files', []))
        if audio:
            return _to_decimal(audio.get('length'))
    except requests.RequestException as e:
        logger.warning('IA metadata error %s: %s', identifier, e)
    return None


def _identifier_from_track_id(track_id: str) -> str | None:
    # track_id format: TRK-IA-{identifier}
    if track_id.startswith('TRK-IA-'):
        return track_id[len('TRK-IA-'):]
    return None


def run(dry_run: bool, limit: int, workers: int):
    table = boto3.resource('dynamodb', region_name=REGION).Table(TABLE)

    updated = skipped = errors = 0
    last_key = None

    scan_kwargs = {
        'FilterExpression': (
            Attr('source_platform').eq('internet_archive') &
            Attr('duration_sec').not_exists()
        ),
        'ProjectionExpression': 'track_id',
    }

    logger.info('=== duration backfill start  dry_run=%s  workers=%d ===', dry_run, workers)

    def _process(track_id: str) -> str:
        """Returns 'updated', 'skipped', or 'error'."""
        identifier = _identifier_from_track_id(track_id)
        if not identifier:
            return 'skipped'

        duration = _fetch_duration(identifier)
        if duration is None:
            return 'skipped'

        if dry_run:
            logger.info('DRY-RUN  %s  duration_sec=%s', track_id, duration)
            return 'updated'

        try:
            table.update_item(
                Key={'track_id': track_id},
                UpdateExpression='SET duration_sec = :d',
                ExpressionAttributeValues={':d': duration},
            )
            return 'updated'
        except ClientError as e:
            logger.error('update failed %s: %s', track_id, e)
            return 'error'

    while True:
        if last_key:
            scan_kwargs['ExclusiveStartKey'] = last_key

        resp     = table.scan(**scan_kwargs)
        items    = resp.get('Items', [])
        last_key = resp.get('LastEvaluatedKey')

        track_ids = [item['track_id'] for item in items]

        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_process, tid): tid for tid in track_ids}
                for future in as_completed(futures):
                    result = future.result()
                    if result == 'updated':   updated += 1
                    elif result == 'skipped': skipped += 1
                    else:                     errors  += 1
                    if limit and updated >= limit:
                        break
        else:
            for tid in track_ids:
                result = _process(tid)
                if result == 'updated':   updated += 1
                elif result == 'skipped': skipped += 1
                else:                     errors  += 1
                if result != 'skipped':
                    time.sleep(RATE_SEC)  # only rate-limit actual IA requests
                if limit and (updated + errors) >= limit:
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
    parser.add_argument('--limit',   type=int, default=0)
    parser.add_argument('--workers', type=int, default=1,
                        help='Parallel IA requests (default 1, max recommended 3)')
    args = parser.parse_args()
    run(args.dry_run, args.limit, args.workers)


if __name__ == '__main__':
    main()
