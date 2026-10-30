import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal

import http.client
import requests
from requests.adapters import HTTPAdapter
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from .base_adapter import BaseAdapter

# ccMixter sends response headers that exceed Python's default 65536 byte limit
# (large JSON payloads embedded in headers). Patch the limit up to 1MB.
http.client._MAXLINE = 1_000_000
http.client._MAXHEADERS = 1000

logger = logging.getLogger(__name__)

CCMIXTER_API_URL = "https://ccmixter.org/api/query"
PAGE_SIZE = 50   # >50 causes LineTooLong header crash on ccMixter's server

HEADERS = {"User-Agent": "Mozilla/5.0"}

# upload_type values that are streamable music
MUSIC_TYPES = {"remix", "original", "sample", "acappella", "instrumental", "media"}


class CCMixterAdapter(BaseAdapter):

    def fetch(self, page: int = 0) -> list[dict]:
        params = {
            "format":  "json",
            "limit":   PAGE_SIZE,
            "offset":  page * PAGE_SIZE,
            "order":   "date_desc",
        }
        try:
            resp = requests.get(CCMIXTER_API_URL, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            if not resp.text.strip():
                return []
            results = resp.json()
            logger.info("ccMixter page %d: fetched %d records", page, len(results))
            return results if isinstance(results, list) else []
        except requests.RequestException as e:
            logger.error("ccMixter fetch error page %d: %s", page, e)
            return []

    def normalize(self, raw: dict) -> dict | None:
        upload_id = raw.get("upload_id")
        if not upload_id:
            return None

        # Must have a CC license
        license_url = raw.get("license_url", "")
        if "creativecommons.org" not in license_url:
            return None

        # Pick the best MP3 from the files array
        mp3_url = self._pick_mp3(raw.get("files", []))
        if not mp3_url:
            return None

        now = datetime.now(timezone.utc).isoformat()

        user_name  = raw.get("user_name", "")
        real_name  = (raw.get("user_real_name") or user_name).strip() or "Unknown Artist"
        artist_id  = f"ART-CCM-{hashlib.md5(user_name.encode()).hexdigest()[:8]}"
        track_id   = f"TRK-CCM-{upload_id}"
        title      = str(raw.get("upload_name") or f"Track {upload_id}").strip()
        source_url = raw.get("file_page_url") or f"https://ccmixter.org/files/{user_name}/{upload_id}"

        # Tags: usertags from upload_extra are the cleanest genre/mood tags
        extra    = raw.get("upload_extra") or {}
        if isinstance(extra, str):
            import json as _json
            try:
                extra = _json.loads(extra)
            except Exception:
                extra = {}
        usertags = [t.strip() for t in str(extra.get("usertags") or "").split(",") if t.strip()]
        _noise = {"mp3", "44k", "stereo", "VBR", "archive", "zip", "flac", "audio",
                  "non_commercial", "attribution", "wav", "ogg", "aiff"}
        systags  = [t.strip() for t in str(extra.get("systags") or "").split(",")
                    if t.strip() and t.strip() not in _noise]
        all_tags = list(dict.fromkeys(usertags + systags))  # deduped, usertags first

        genre = usertags[0] if usertags else (systags[0] if systags else "Unknown")

        upload_type = (raw.get("upload_type") or "").lower()
        # Map upload_type to content_type
        content_type = "music"

        attribution = f'"{title}" by {real_name} — {license_url} — {source_url}'

        item: dict = {
            "track_id":         track_id,
            "title":            title,
            "content_type":     content_type,
            "artist_id":        artist_id,
            "artist_name":      real_name,
            # ccMixter has no album concept — use artist name as album grouping
            "album_id":         f"ALB-CCM-{artist_id}",
            "album_title":      f"{real_name} on ccMixter",
            "genre":            genre,
            "tags":             all_tags,
            "source_platform":  "ccmixter",
            "stream_url":       mp3_url,
            "source_url":       source_url,
            "license_type":     license_url,
            "is_streamable":    True,
            "is_downloadable":  True,
            "attribution_text": attribution,
            "play_count":       0,
            "dataset_version":  "v1.0.0",
            "health_status":    "active",
            "http_status_code": 200,
            "last_checked_at":  now,
            "added_at":         now,
            "last_updated_at":  now,
        }

        # Sparse fields
        if upload_type:
            item["upload_type"] = upload_type

        return item

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_mp3(self, files: list) -> str | None:
        """Return the download_url of the best MP3 in the files list."""
        mp3s = [
            f for f in files
            if isinstance(f, dict)
            and f.get("file_name", "").lower().endswith(".mp3")
            and f.get("download_url")
        ]
        if not mp3s:
            return None
        # Prefer the shortest filename (usually the primary, not a numbered variant)
        mp3s.sort(key=lambda f: len(f.get("file_name", "")))
        return mp3s[0]["download_url"]
