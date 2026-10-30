"""
Wikimedia Commons audio adapter.

Ingests CC-licensed audio files from Wikimedia Commons by crawling
genre-based categories. Audio files are .ogg/.flac/.wav — all supported
by modern browsers and served with CORS: *.

API docs: https://www.mediawiki.org/wiki/API:Main_page
Rate limit: 200 req/s unauthenticated (we stay well under with 1 worker + sleep)

Usage (via test script):
  python -u tests/test_ingest_wikimedia.py [--genre classical] [--limit 500] [--dry-run]
"""
import re
import time
import hashlib
import logging
from datetime import datetime, timezone

import requests

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

API      = 'https://commons.wikimedia.org/w/api.php'
HEADERS  = {'User-Agent': 'MusicMetaIndex/1.0 (https://github.com/Shannon-Goddard/music)'}
RATE_SLEEP = 0.5  # seconds between API calls

# CC licenses we accept — maps Wikimedia short name to our license_type URL
CC_LICENSES = {
    'cc0':        'https://creativecommons.org/publicdomain/zero/1.0/',
    'cc-zero':    'https://creativecommons.org/publicdomain/zero/1.0/',
    'pd':         'https://creativecommons.org/publicdomain/mark/1.0/',
    'public domain': 'https://creativecommons.org/publicdomain/mark/1.0/',
    'cc-by-1.0':  'https://creativecommons.org/licenses/by/1.0/',
    'cc-by-2.0':  'https://creativecommons.org/licenses/by/2.0/',
    'cc-by-2.5':  'https://creativecommons.org/licenses/by/2.5/',
    'cc-by-3.0':  'https://creativecommons.org/licenses/by/3.0/',
    'cc-by-4.0':  'https://creativecommons.org/licenses/by/4.0/',
    'cc-by-sa-1.0': 'https://creativecommons.org/licenses/by-sa/1.0/',
    'cc-by-sa-2.0': 'https://creativecommons.org/licenses/by-sa/2.0/',
    'cc-by-sa-2.5': 'https://creativecommons.org/licenses/by-sa/2.5/',
    'cc-by-sa-3.0': 'https://creativecommons.org/licenses/by-sa/3.0/',
    'cc-by-sa-4.0': 'https://creativecommons.org/licenses/by-sa/4.0/',
}

# Genre categories to ingest — maps our genre tag to Wikimedia category
GENRE_CATEGORIES = {
    'classical':   'Category:Audio_files_of_classical_music',
    'jazz':        'Category:Audio_files_of_jazz_music',
    'blues':       'Category:Audio_files_of_blues',
    'folk':        'Category:Audio_files_of_folk_music',
    'electronic':  'Category:Audio_files_of_electronic_music',
    'rock':        'Category:Audio_files_of_rock_music',
    'pop':         'Category:Audio_files_of_pop_music',
    'hip-hop':     'Category:Audio_files_of_hip_hop_music',
    'country':     'Category:Audio_files_of_country_music',
    'reggae':      'Category:Audio_files_of_reggae',
    'funk':        'Category:Audio_files_of_funk',
    'ragtime':     'Category:Audio_files_of_ragtime_music',
    'world':       'Category:Audio_files_of_world_music',
    'traditional': 'Category:Audio_files_of_traditional_music',
    'instrumental':'Category:Audio_files_of_instrumental_music',
}

# Audio MIME types we accept
AUDIO_MIMES = {'audio/ogg', 'audio/mpeg', 'audio/flac', 'audio/wav', 'audio/webm', 'application/ogg'}


def _strip_html(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s or '').strip()


def _license_url(em: dict) -> str | None:
    """Extract a CC license URL from extmetadata, or None if not CC."""
    # Try LicenseUrl first
    url = em.get('LicenseUrl', {}).get('value', '')
    if url and 'creativecommons.org' in url:
        return url.rstrip('/')

    # Fall back to License short name
    short = em.get('License', {}).get('value', '').lower().strip()
    if short in CC_LICENSES:
        return CC_LICENSES[short]

    short2 = em.get('LicenseShortName', {}).get('value', '').lower().strip()
    for key in CC_LICENSES:
        if key in short2:
            return CC_LICENSES[key]

    return None


class WikimediaAdapter(BaseAdapter):
    """
    Fetches audio files from a Wikimedia Commons genre category.

    Args:
        genre:    our genre tag (key in GENRE_CATEGORIES)
        category: override with a custom Wikimedia category title
    """

    def __init__(self, genre: str = 'classical', category: str = ''):
        self.genre    = genre
        self.category = category or GENRE_CATEGORIES.get(genre, f'Category:Audio_files_of_{genre}_music')
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._cmcontinue = None   # pagination token
        self._page       = 0

    def _get(self, params: dict) -> dict:
        params['format'] = 'json'
        try:
            r = self._session.get(API, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.warning('Wikimedia API error: %s', e)
            return {}

    def fetch(self, page: int = 0) -> list[dict]:
        """Fetch one page of file titles from the category, then batch-fetch metadata."""
        # On first call or sequential calls, use stored continue token
        params = {
            'action':  'query',
            'list':    'categorymembers',
            'cmtitle': self.category,
            'cmtype':  'file',
            'cmlimit': 50,
        }
        if self._cmcontinue:
            params['cmcontinue'] = self._cmcontinue

        data = self._get(params)
        time.sleep(RATE_SLEEP)

        members = data.get('query', {}).get('categorymembers', [])
        if not members:
            return []

        # Save continue token for next call
        self._cmcontinue = data.get('continue', {}).get('cmcontinue')

        # Batch fetch imageinfo for all titles in one request (up to 50)
        titles = '|'.join(m['title'] for m in members)
        meta = self._get({
            'action':  'query',
            'titles':  titles,
            'prop':    'imageinfo',
            'iiprop':  'url|mime|size|extmetadata',
        })
        time.sleep(RATE_SLEEP)

        pages = meta.get('query', {}).get('pages', {})
        self._page += 1
        return list(pages.values())

    def normalize(self, raw: dict) -> dict | None:
        """Convert a Wikimedia page record to our schema. Returns None to skip."""
        ii = raw.get('imageinfo', [{}])
        if not ii:
            return None
        ii = ii[0]

        mime = ii.get('mime', '')
        if mime not in AUDIO_MIMES:
            return None

        em  = ii.get('extmetadata', {})
        url = ii.get('url', '')
        if not url:
            return None

        # Strip UTM params from URL
        stream_url = url.split('?')[0]

        # License check — skip non-CC
        license_url = _license_url(em)
        if not license_url:
            return None

        # Title — prefer ObjectName, fall back to filename
        title = _strip_html(em.get('ObjectName', {}).get('value', ''))
        if not title:
            title = raw.get('title', '').replace('File:', '').rsplit('.', 1)[0].strip()

        # Artist
        artist = _strip_html(em.get('Artist', {}).get('value', '')) or \
                 _strip_html(em.get('Attribution', {}).get('value', '')) or \
                 'Unknown Artist'

        # Description
        desc = _strip_html(em.get('ImageDescription', {}).get('value', ''))

        # Genre tags from Categories field
        cats = em.get('Categories', {}).get('value', '')
        tags = _extract_tags(cats, self.genre)

        # Duration
        duration = ii.get('duration')
        if duration:
            try:
                duration = float(duration)
            except (ValueError, TypeError):
                duration = None

        # Stable track ID from stream URL
        url_hash  = hashlib.md5(stream_url.encode()).hexdigest()[:10]
        track_id  = f'TRK-WM-{url_hash}'
        artist_id = f'ART-WM-{hashlib.md5(artist.encode()).hexdigest()[:8]}'
        album_id  = f'ALB-WM-{url_hash}'

        source_url = raw.get('imageinfo', [{}])[0].get('descriptionurl', '')

        attribution = f'"{title}" by {artist} — {license_url} — {source_url}'

        return {
            'track_id':         track_id,
            'title':            title,
            'artist_id':        artist_id,
            'artist_name':      artist,
            'album_id':         album_id,
            'album_title':      title,
            'track_number':     None,
            'genre':            self.genre,
            'tags':             tags,
            'language':         None,
            'content_type':     'music',
            'duration_sec':     duration,
            'cover_art_url':    None,
            'stream_url':       stream_url,
            'source_url':       source_url,
            'source_platform':  'wikimedia',
            'wm_category':      self.category,
            'format':           _mime_to_fmt(mime),
            'license_type':     license_url,
            'is_streamable':    True,
            'is_downloadable':  True,
            'attribution_text': attribution,
            'health_status':    'active',
            'last_checked_at':  datetime.now(timezone.utc).isoformat(),
            'last_updated_at':  datetime.now(timezone.utc).isoformat(),
            'added_at':         datetime.now(timezone.utc).isoformat(),
            'dataset_version':  'v1.0.0',
        }

    def has_more(self) -> bool:
        """Returns False when category pagination is exhausted."""
        return self._page == 0 or self._cmcontinue is not None


def _mime_to_fmt(mime: str) -> str:
    return {
        'audio/ogg':     'ogg',
        'application/ogg': 'ogg',
        'audio/mpeg':    'mp3',
        'audio/flac':    'flac',
        'audio/wav':     'wav',
        'audio/webm':    'webm',
    }.get(mime, 'ogg')


def _extract_tags(categories_str: str, genre: str) -> list[str]:
    """Pull useful tags from the pipe-separated Wikimedia categories string."""
    tags = [genre]
    if not categories_str:
        return tags
    for cat in categories_str.split('|'):
        cat = cat.strip().lower()
        # Skip noisy meta-categories
        if any(skip in cat for skip in ['files', 'media', 'upload', 'loanword', 'language', 'reviewed']):
            continue
        # Keep short descriptive ones
        if 2 < len(cat) < 40:
            tags.append(cat)
    return list(dict.fromkeys(tags))[:10]  # dedupe, cap at 10
