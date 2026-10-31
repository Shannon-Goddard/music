"""
Freesound audio adapter.

Ingests CC-licensed music from Freesound by querying genre tags with a
duration filter (>=30s) to exclude sound effects and short clips.

API docs: https://freesound.org/docs/api/
Auth: API key via token param (read-only, no OAuth needed for search)
Rate limit: 2,000 req/day on free tier — we stay well under with sleeps.

Credentials stored in AWS Secrets Manager: freesound-api
  { "client_id": "...", "api_key": "..." }

Usage (via test script):
  python -u tests/test_ingest_freesound.py [--tag jazz] [--limit 500] [--dry-run]
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

API_BASE   = 'https://freesound.org/apiv2'
RATE_SLEEP  = 1.0   # seconds between requests — bumped to reduce throttle risk
RETRY_WAIT  = 60    # seconds to wait after a hard timeout before retrying
PAGE_SIZE  = 150   # Freesound max is 150

# CC licenses we accept
CC_LICENSES = {
    'creativecommons.org/publicdomain/zero',
    'creativecommons.org/licenses/by/',
    'creativecommons.org/licenses/by-sa/',
    'creativecommons.org/licenses/by-nc/',
    'creativecommons.org/licenses/by-nc-sa/',
}

# Fields to request from the API
FIELDS = 'id,name,username,duration,license,tags,description,created,previews'

# Genre tags to sweep — appended with " music" to bias results toward music
FREESOUND_TAGS = [
    'jazz', 'classical', 'blues', 'folk', 'electronic', 'ambient',
    'rock', 'pop', 'hip-hop', 'reggae', 'country', 'soul', 'funk',
    'metal', 'punk', 'latin', 'world', 'instrumental', 'acoustic',
    'piano', 'guitar', 'orchestral', 'chillout', 'lofi',
]


def _get_api_key() -> str:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    secret = client.get_secret_value(SecretId='freesound-api')
    return json.loads(secret['SecretString'])['api_key']


def _is_cc(license_url: str) -> bool:
    return any(fragment in license_url for fragment in CC_LICENSES)


def _strip_html(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s or '').strip()


class FreesoundAdapter(BaseAdapter):
    """
    Fetches music tracks from Freesound by genre tag query.

    Args:
        tag: genre tag to search (e.g. 'jazz')
    """

    def __init__(self, tag: str = 'jazz'):
        self.tag      = tag
        self._api_key = None
        self._page    = 1        # Freesound pages are 1-indexed
        self._total   = None     # total results for this query
        self._fetched = 0

    def _key(self) -> str:
        if not self._api_key:
            self._api_key = _get_api_key()
        return self._api_key

    def _make_session(self) -> requests.Session:
        s = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=2,          # 2s, 4s, 8s
            status_forcelist={429, 500, 502, 503, 504},
            allowed_methods={'GET'},
            raise_on_status=False,
        )
        s.mount('https://', HTTPAdapter(max_retries=retry))
        return s

    def fetch(self, page: int = 0) -> list[dict]:
        """Fetch one page. `page` arg ignored — uses internal cursor."""
        params = {
            'token':     self._key(),
            'query':     f'{self.tag} music',
            'filter':    (
                'license:("Creative Commons 0" OR "Attribution" OR '
                '"Attribution NonCommercial" OR "Attribution ShareAlike" OR '
                '"Attribution NonCommercial ShareAlike") '
                'duration:[30 TO *]'
            ),
            'fields':    FIELDS,
            'page_size': PAGE_SIZE,
            'page':      self._page,
        }
        for attempt in range(3):
            try:
                r = self._make_session().get(
                    f'{API_BASE}/search/text/', params=params, timeout=30
                )
                if r.status_code == 429:
                    wait = int(r.headers.get('Retry-After', RETRY_WAIT))
                    logger.warning('Freesound rate limited — waiting %ds', wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                data = r.json()
                time.sleep(RATE_SLEEP)

                if self._total is None:
                    self._total = data.get('count', 0)
                    logger.info('Freesound [%s]: %d total results', self.tag, self._total)

                results = data.get('results', [])
                self._fetched += len(results)
                self._page    += 1
                return results
            except requests.RequestException as e:
                wait = RETRY_WAIT * (attempt + 1)
                logger.warning('Freesound timeout tag=%s page=%d attempt=%d — retrying in %ds',
                               self.tag, self._page, attempt + 1, wait)
                time.sleep(wait)
        logger.error('Freesound tag=%s page=%d failed after 3 attempts — skipping',
                     self.tag, self._page)
        self._page += 1
        return []

    def normalize(self, raw: dict) -> dict | None:
        fid = raw.get('id')
        if not fid:
            return None

        license_url = raw.get('license', '')
        if not _is_cc(license_url):
            return None

        previews = raw.get('previews') or {}
        stream_url = (
            previews.get('preview-hq-mp3') or
            previews.get('preview-hq-ogg') or
            previews.get('preview-lq-mp3') or
            previews.get('preview-lq-ogg', '')
        )
        if not stream_url:
            return None

        fmt = 'mp3' if stream_url.endswith('.mp3') else 'ogg'

        title       = (raw.get('name') or '').strip() or f'Sound {fid}'
        username    = (raw.get('username') or 'Unknown Artist').strip()
        artist_id   = f'ART-FS-{hashlib.md5(username.encode()).hexdigest()[:8]}'
        track_id    = f'TRK-FS-{fid}'
        source_url  = f'https://freesound.org/people/{username}/sounds/{fid}/'
        description = _strip_html(raw.get('description', ''))

        tags = [t.lower() for t in (raw.get('tags') or []) if t]
        genre = self.tag  # use the query tag as genre; refine from tags if possible
        for t in tags:
            if t in {g for g in FREESOUND_TAGS}:
                genre = t
                break

        duration = None
        raw_dur = raw.get('duration')
        if raw_dur is not None:
            try:
                duration = Decimal(str(float(raw_dur))).quantize(Decimal('0.01'))
            except Exception:
                pass

        release_year = None
        created = raw.get('created', '')
        if created and len(created) >= 4:
            try:
                release_year = int(created[:4])
            except ValueError:
                pass

        now = datetime.now(timezone.utc).isoformat()
        attribution = f'"{title}" by {username} — {license_url} — {source_url}'

        item = {
            'track_id':         track_id,
            'title':            title,
            'content_type':     'music',
            'artist_id':        artist_id,
            'artist_name':      username,
            'album_id':         f'ALB-FS-{artist_id}',   # no album concept; group by artist
            'album_title':      f'{username} on Freesound',
            'genre':            genre,
            'tags':             tags[:10],
            'source_platform':  'freesound',
            'stream_url':       stream_url,
            'source_url':       source_url,
            'format':           fmt,
            'license_type':     license_url,
            'is_streamable':    True,
            'is_downloadable':  False,   # previews only; full download needs OAuth
            'attribution_text': attribution,
            'play_count':       0,
            'dataset_version':  'v1.0.0',
            'health_status':    'active',
            'last_checked_at':  now,
            'added_at':         now,
            'last_updated_at':  now,
        }

        if duration is not None:
            item['duration_sec'] = duration
        if release_year:
            item['release_year'] = release_year
        if description:
            item['description'] = description[:500]

        return item

    def has_more(self) -> bool:
        if self._total is None:
            return True   # haven't fetched yet
        return self._fetched < self._total
