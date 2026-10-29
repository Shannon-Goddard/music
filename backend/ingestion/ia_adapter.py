import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

IA_SEARCH_URL = "https://archive.org/advancedsearch.php"
IA_METADATA_URL = "https://archive.org/metadata"
PAGE_SIZE = 50

# Only ingest openly licensed audio
ALLOWED_LICENSES = (
    "creativecommons",
    "publicdomain",
)

# Target music collections specifically — excludes podcasts, sermons, lectures
IA_SEARCH_QUERY = (
    "mediatype:audio AND "
    "licenseurl:(*creativecommons* OR *publicdomain*) AND "
    "subject:(music OR song OR album OR instrumental OR jazz OR rock OR "
    "classical OR folk OR electronic OR blues OR ambient OR pop OR hip-hop)"
)


class IAAdapter(BaseAdapter):

    def fetch(self, page: int = 0) -> list[dict]:
        params = {
            "q": IA_SEARCH_QUERY,
            "fl[]": ["identifier", "title", "creator", "subject", "year", "licenseurl"],
            "rows": PAGE_SIZE,
            "page": page + 1,
            "output": "json",
        }
        try:
            response = requests.get(IA_SEARCH_URL, params=params, timeout=15)
            response.raise_for_status()
            docs = response.json().get("response", {}).get("docs", [])
            logger.info("IA page %d: fetched %d records", page, len(docs))
            return docs
        except requests.RequestException as e:
            logger.error("IA fetch error on page %d: %s", page, e)
            return []

    def normalize(self, raw: dict) -> dict | None:
        identifier = raw.get("identifier")
        if not identifier:
            return None

        # Verify license is allowed
        license_url = raw.get("licenseurl", "")
        if not any(allowed in license_url.lower() for allowed in ALLOWED_LICENSES):
            return None

        # Fetch full item metadata to get file list
        meta = self._fetch_metadata(identifier)
        if not meta:
            return None

        mp3_file = self._pick_mp3(meta.get("files", []))
        if not mp3_file:
            return None

        stream_url = f"https://archive.org/download/{identifier}/{mp3_file['name']}"

        # Pre-flight check — skip tracks that require login to stream
        if not self._is_publicly_streamable(stream_url):
            logger.info("IA: skipping non-public stream for %s", identifier)
            return None
        source_url = f"https://archive.org/details/{identifier}"
        track_id = f"TRK-IA-{identifier}"
        now = datetime.now(timezone.utc).isoformat()

        title = raw.get("title") or mp3_file.get("title") or identifier
        creator = raw.get("creator") or "Unknown Artist"
        artist_id = f"ART-IA-{hashlib.md5(creator.encode()).hexdigest()[:8]}"

        item = {
            "track_id": track_id,
            "title": title,
            "release_year": self._to_int(raw.get("year")),
            "artist_id": artist_id,
            "artist_name": creator,
            "album_id": f"ALB-IA-{identifier}",
            "album_title": raw.get("title") or identifier,
            "genre": self._first(raw.get("subject")) or "Unknown",
            "tags": self._to_list(raw.get("subject")),
            "source_platform": "internet_archive",
            "stream_url": stream_url,
            "source_url": source_url,
            "format": "mp3",
            "audio_hash_md5": mp3_file.get("md5") or "",
            "license_type": license_url,
            "is_streamable": True,
            "is_downloadable": True,
            "attribution_text": f'"{title}" by {creator} — {license_url} — {source_url}',
            "play_count": 0,
            "dataset_version": "v1.0.0",
            "health_status": "active",
            "http_status_code": 200,
            "last_checked_at": now,
            "added_at": now,
            "last_updated_at": now,
        }

        # Sparse fields — omit entirely if None so GSIs stay clean
        duration = self._to_decimal(mp3_file.get("length"))
        if duration is not None:
            item["duration_sec"] = duration

        bitrate = self._to_int(mp3_file.get("bitrate"))
        if bitrate is not None:
            item["bitrate_kbps"] = bitrate

        track_number = self._to_int(mp3_file.get("track"))
        if track_number is not None:
            item["track_number"] = track_number

        cover = self._cover_art_url(identifier, meta.get("files", []))
        if cover:
            item["cover_art_url"] = cover

        return item

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_publicly_streamable(self, url: str) -> bool:
        """Return True only if the stream URL is publicly accessible without auth."""
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            return response.status_code in {200, 206, 301, 302}
        except requests.RequestException:
            return False

    def _fetch_metadata(self, identifier: str) -> dict | None:
        try:
            response = requests.get(f"{IA_METADATA_URL}/{identifier}", timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error("IA metadata fetch failed for %s: %s", identifier, e)
            return None

    def _pick_mp3(self, files: list[dict]) -> dict | None:
        mp3s = [f for f in files if f.get("name", "").lower().endswith(".mp3")]
        if not mp3s:
            return None
        mp3s.sort(key=lambda f: self._to_int(f.get("bitrate")) or 0, reverse=True)
        return mp3s[0]

    def _cover_art_url(self, identifier: str, files: list[dict]) -> str | None:
        for f in files:
            name = f.get("name", "").lower()
            if name.endswith((".jpg", ".jpeg", ".png")) and "cover" in name:
                return f"https://archive.org/download/{identifier}/{f['name']}"
        return None

    def _first(self, value) -> str | None:
        if isinstance(value, list):
            return value[0] if value else None
        return value or None

    def _to_list(self, value) -> list:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [value]
        return []

    def _to_decimal(self, value) -> Decimal | None:
        try:
            return Decimal(str(float(value))).quantize(Decimal('0.01'))
        except (TypeError, ValueError, InvalidOperation):
            return None

    def _to_float(self, value) -> Decimal | None:
        try:
            return Decimal(str(float(value))).quantize(Decimal('0.01'))
        except (TypeError, ValueError, InvalidOperation):
            return None

    def _to_int(self, value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
