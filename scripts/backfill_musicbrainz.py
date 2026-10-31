"""
MusicBrainz + Cover Art Archive backfill.

Scans DynamoDB for records where cover_art_url is null, queries MusicBrainz
for a recording match, then fetches cover art from Cover Art Archive.
Also backfills musicbrainz_artist_id and improves genre tags where possible.

Usage:
  python -u scripts/backfill_musicbrainz.py [--type music] [--limit 1000] [--dry-run]

Options:
  --type TYPE     content_type to target (default: music). Use 'all' for everything.
  --limit N       max records to process (default: unlimited)
  --dry-run       print matches without writing to DynamoDB
  --resume TOKEN  ExclusiveStartKey token file to resume a scan

Rate limit: MusicBrainz allows ~1 req/sec sustained. We use 3 workers with
a 1.1s sleep between requests per worker = ~2.7 req/sec burst, safe in practice.

Results per run are logged to scripts/mb_backfill.log
"""
import sys
import json
import time
import logging
import argparse
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import boto3
import requests
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

# ── Config ────────────────────────────────────────────────────────────

TABLE_NAME  = os.environ.get('DYNAMODB_TABLE', 'music-tracks')
REGION      = os.environ.get('AWS_REGION', 'us-east-1')
MB_BASE     = 'https://musicbrainz.org/ws/2'
CAA_BASE    = 'https://coverartarchive.org'
USER_AGENT  = 'MusicMetaIndex/1.0 (https://github.com/Shannon-Goddard/music)'
WORKERS     = 3
RATE_SLEEP  = 1.1   # seconds between MB requests per worker
SCAN_LIMIT  = 100   # DynamoDB scan page size
RESUME_FILE = 'scripts/mb_resume_token.json'
LOG_FILE    = 'scripts/mb_backfill.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE),
    ]
)
logger = logging.getLogger(__name__)

# ── AWS ───────────────────────────────────────────────────────────────

_table = None

def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource('dynamodb', region_name=REGION).Table(TABLE_NAME)
    return _table


def _scan_needs_art(content_type_filter: str, collection_filter: str, start_key: dict | None) -> tuple[list, dict | None]:
    """Return one page of records missing cover_art_url."""
    kwargs = {
        'FilterExpression': Attr('cover_art_url').not_exists() & Attr('health_status').eq('active'),
        'Limit': SCAN_LIMIT,
        'ProjectionExpression':
            'track_id, title, artist_name, album_title, genre, '
            'source_platform, ia_collection, content_type',
    }
    if content_type_filter != 'all':
        kwargs['FilterExpression'] &= Attr('content_type').eq(content_type_filter)
    if collection_filter:
        kwargs['FilterExpression'] &= Attr('ia_collection').eq(collection_filter)
    if start_key:
        kwargs['ExclusiveStartKey'] = start_key
    try:
        resp = _get_table().scan(**kwargs)
        return resp.get('Items', []), resp.get('LastEvaluatedKey')
    except ClientError as e:
        logger.error('DynamoDB scan error: %s', e)
        return [], None


def _update_record(track_id: str, updates: dict, dry_run: bool) -> bool:
    if dry_run:
        logger.info('DRY-RUN would update %s: %s', track_id, list(updates.keys()))
        return True
    expr_parts, names, values = [], {}, {}
    for i, (k, v) in enumerate(updates.items()):
        placeholder = f'#f{i}'
        val_key     = f':v{i}'
        names[placeholder] = k
        values[val_key]    = v
        expr_parts.append(f'{placeholder} = {val_key}')
    names['#lu']  = 'last_updated_at'
    values[':lu'] = datetime.now(timezone.utc).isoformat()
    expr_parts.append('#lu = :lu')
    try:
        _get_table().update_item(
            Key={'track_id': track_id},
            UpdateExpression='SET ' + ', '.join(expr_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return True
    except ClientError as e:
        logger.error('DynamoDB update error for %s: %s', track_id, e)
        return False

# ── MusicBrainz ───────────────────────────────────────────────────────

_session = requests.Session()
_session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})


def _mb_get(path: str, params: dict) -> dict | None:
    url = f'{MB_BASE}/{path}'
    try:
        r = _session.get(url, params=params, timeout=15)
        if r.status_code == 429:
            logger.warning('MB rate limited — sleeping 10s')
            time.sleep(10)
            return None
        if r.status_code != 200:
            return None
        return r.json()
    except requests.RequestException as e:
        logger.warning('MB request error: %s', e)
        return None


# Patterns common in 78rpm/georgeblood IA titles
_TITLE_NOISE = re.compile(
    r'\s*[\(\[].*?[\)\]]'          # (Part 1), [matrix XYZ]
    r'|\s*-\s*take\s+\d+$'         # - take 2
    r'|\s*,?\s*no\.?\s*\d+$',      # No. 3
    re.IGNORECASE
)
_ARTIST_NOISE = re.compile(
    r'\s+and\s+(his|her|the)\s+.*$'   # and His Orchestra / and Her Band
    r'|\s+&\s+.*$'                      # & His Hot Five
    r'|\s+with\s+.*$'                   # with Bix Beiderbecke / with the Rhythm Boys
    r'|\s+feat\.?.*$'                   # feat. someone
    r'|\s+accompanied\s+by.*$',         # accompanied by ...
    re.IGNORECASE
)


def _clean_title(s: str) -> str:
    return _TITLE_NOISE.sub('', s).strip()


def _clean_artist(s: str) -> str:
    return _ARTIST_NOISE.sub('', s).strip()


def _search_recording(title: str, artist: str) -> dict | None:
    """Search MusicBrainz for a recording. Returns best match or None."""
    def _esc(s): return s.replace('"', '\\"').replace('(', '').replace(')', '')

    # Try progressively looser queries
    clean_title  = _clean_title(title)
    clean_artist = _clean_artist(artist)

    queries = [
        f'recording:"{_esc(clean_title)}" AND artist:"{_esc(clean_artist)}"',
        f'recording:"{_esc(clean_title)}" AND artist:"{_esc(artist)}"',
        f'recording:"{_esc(title)}" AND artist:"{_esc(clean_artist)}"',
    ]
    # Deduplicate while preserving order
    unique_queries, seen_q = [], set()
    for q in queries:
        if q not in seen_q:
            unique_queries.append(q)
            seen_q.add(q)

    for query in unique_queries:
        data = _mb_get('recording', {'query': query, 'limit': 5, 'fmt': 'json'})
        time.sleep(RATE_SLEEP)
        if not data or not data.get('recordings'):
            continue
        for rec in data['recordings']:
            if rec.get('score', 0) < 60:
                break
            releases = rec.get('releases', [])
            if releases:
                return {
                    'recording_id':  rec.get('id'),
                    'release_id':    releases[0].get('id'),
                    'artist_credit': rec.get('artist-credit', []),
                    'tags':          rec.get('tags', []),
                }
    return None


def _get_cover_art(release_id: str) -> str | None:
    """Fetch front cover URL from Cover Art Archive."""
    try:
        r = _session.get(
            f'{CAA_BASE}/release/{release_id}',
            timeout=10,
            allow_redirects=True,
        )
        time.sleep(RATE_SLEEP)
        if r.status_code != 200:
            return None
        images = r.json().get('images', [])
        for img in images:
            if img.get('front'):
                # Prefer 500px thumbnail, fall back to original
                thumbs = img.get('thumbnails', {})
                return thumbs.get('500') or thumbs.get('large') or img.get('image')
    except (requests.RequestException, ValueError):
        pass
    return None


def _get_artist_mb_id(artist_credits: list) -> str | None:
    if not artist_credits:
        return None
    first = artist_credits[0]
    if isinstance(first, dict):
        return first.get('artist', {}).get('id')
    return None


def _top_tags(tags: list, n: int = 5) -> list[str]:
    """Return top N tag names sorted by count."""
    sorted_tags = sorted(tags, key=lambda t: t.get('count', 0), reverse=True)
    return [t['name'] for t in sorted_tags[:n] if t.get('name')]

# ── Per-record enrichment ─────────────────────────────────────────────

def enrich_record(record: dict, dry_run: bool) -> str:
    """
    Attempt to enrich one record. Returns status string for logging.
    'hit'     — cover art found and written
    'partial' — artist ID or tags updated but no cover art
    'miss'    — no MB match
    'skip'    — skipped (Jamendo already has art, etc.)
    """
    track_id    = record['track_id']
    title       = record.get('title', '').strip()
    artist      = record.get('artist_name', '').strip()

    if not title or not artist or artist == 'Unknown Artist':
        return 'skip'

    match = _search_recording(title, artist)
    if not match:
        return 'miss'

    updates = {}

    # Cover art
    release_id = match.get('release_id')
    if release_id:
        cover = _get_cover_art(release_id)
        if cover:
            updates['cover_art_url'] = cover

    # MusicBrainz artist ID
    mb_artist_id = _get_artist_mb_id(match.get('artist_credit', []))
    if mb_artist_id:
        updates['musicbrainz_artist_id'] = mb_artist_id

    # Better genre tags from MB folksonomy
    mb_tags = _top_tags(match.get('tags', []))
    if mb_tags and not record.get('genre') or record.get('genre') == 'Unknown':
        updates['genre'] = mb_tags[0]
    if mb_tags:
        updates['mb_tags'] = mb_tags

    # MusicBrainz recording ID
    if match.get('recording_id'):
        updates['musicbrainz_recording_id'] = match['recording_id']

    if not updates:
        return 'miss'

    _update_record(track_id, updates, dry_run)
    return 'hit' if 'cover_art_url' in updates else 'partial'

# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--type',       default='music', help='content_type filter (default: music, use all for everything)')
    parser.add_argument('--collection',  default='',      help='ia_collection filter e.g. georgeblood, 78rpm (default: all collections)')
    parser.add_argument('--limit',       type=int, default=0, help='max records to process (0 = unlimited)')
    parser.add_argument('--dry-run',     action='store_true')
    args = parser.parse_args()

    logger.info('=== MusicBrainz backfill start ===')
    logger.info('type=%s  collection=%s  limit=%s  dry_run=%s  workers=%d',
                args.type, args.collection or 'all', args.limit or 'unlimited', args.dry_run, WORKERS)

    # Load resume token if exists
    start_key = None
    if os.path.exists(RESUME_FILE):
        try:
            with open(RESUME_FILE) as f:
                start_key = json.load(f)
            logger.info('Resuming from saved token')
        except Exception:
            start_key = None

    hits = misses = partials = skips = errors = total = 0

    while True:
        page, next_key = _scan_needs_art(args.type, args.collection, start_key)
        if not page:
            break

        # Process page in parallel
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(enrich_record, rec, args.dry_run): rec for rec in page}
            for future in as_completed(futures):
                total += 1
                try:
                    status = future.result()
                except Exception as e:
                    logger.error('Worker error: %s', e)
                    errors += 1
                    status = 'error'

                if   status == 'hit':     hits     += 1
                elif status == 'partial': partials += 1
                elif status == 'miss':    misses   += 1
                elif status == 'skip':    skips    += 1

                if total % 50 == 0:
                    logger.info('progress: total=%d  hits=%d  partial=%d  miss=%d  skip=%d  err=%d',
                                total, hits, partials, misses, skips, errors)

        # Save resume token after each page
        if next_key:
            with open(RESUME_FILE, 'w') as f:
                json.dump(next_key, f)
        else:
            if os.path.exists(RESUME_FILE):
                os.remove(RESUME_FILE)

        start_key = next_key

        if args.limit and total >= args.limit:
            logger.info('Reached limit of %d records', args.limit)
            break

        if not next_key:
            break

    logger.info('=== DONE: total=%d  hits=%d  partial=%d  miss=%d  skip=%d  err=%d ===',
                total, hits, partials, misses, skips, errors)
    logger.info('Cover art added to %d records (%.1f%% hit rate)',
                hits, (hits / total * 100) if total else 0)


if __name__ == '__main__':
    main()
