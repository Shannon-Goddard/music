import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import requests

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

JAMENDO_API_URL = "https://api.jamendo.com/v3.0/tracks/"
PAGE_SIZE = 200  # Jamendo max is 200

# Genre tags to sweep — each tag query returns up to thousands of tracks.
# Deduplication by track_id happens in the ingest script.
JAMENDO_TAGS = [
    "electronic", "ambient", "pop", "rock", "jazz", "classical",
    "folk", "hiphop", "metal", "blues", "soul", "reggae",
    "chillwave", "dance", "acoustic", "instrumental", "lounge",
    "experimental", "soundtrack", "world",
]

BASE_PARAMS = {
    "format":      "json",
    "limit":       PAGE_SIZE,
    "include":     "musicinfo",
    "audioformat": "mp32",
    "order":       "releasedate_desc",
}


def _get_client_id() -> str:
    client = boto3.client("secretsmanager", region_name="us-east-1")
    secret = client.get_secret_value(SecretId="music/jamendo")
    import json
    return json.loads(secret["SecretString"])["client_id"]


class JamendoAdapter(BaseAdapter):

    def __init__(self):
        self._client_id = None

    def _cid(self) -> str:
        if not self._client_id:
            self._client_id = _get_client_id()
        return self._client_id

    def fetch(self, page: int = 0, tag: str = "") -> list[dict]:
        params = {
            **BASE_PARAMS,
            "client_id": self._cid(),
            "offset":    page * PAGE_SIZE,
        }
        if tag:
            params["tags"] = tag
        try:
            resp = requests.get(JAMENDO_API_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            logger.info("Jamendo [%s] page %d: fetched %d records", tag or "all", page, len(results))
            return results
        except requests.RequestException as e:
            logger.error("Jamendo fetch error on page %d tag=%s: %s", page, tag, e)
            return []

    def normalize(self, raw: dict) -> dict | None:
        track_id_raw = raw.get("id")
        if not track_id_raw:
            return None

        # Only keep CC-licensed tracks
        license_url = raw.get("license_ccurl", "")
        if not license_url or "creativecommons.org" not in license_url:
            return None

        stream_url = raw.get("audio", "")
        if not stream_url:
            return None

        now = datetime.now(timezone.utc).isoformat()

        track_id   = f"TRK-JM-{track_id_raw}"
        title      = (raw.get("name") or "").strip() or f"Track {track_id_raw}"
        artist_name = (raw.get("artist_name") or "Unknown Artist").strip()
        artist_id  = f"ART-JM-{raw.get('artist_id', hashlib.md5(artist_name.encode()).hexdigest()[:8])}"
        album_id   = f"ALB-JM-{raw.get('album_id', track_id_raw)}"
        album_title = (raw.get("album_name") or title).strip()

        musicinfo  = raw.get("musicinfo") or {}
        tags_obj   = musicinfo.get("tags") or {}
        genres     = tags_obj.get("genres") or []
        vartags    = tags_obj.get("vartags") or []
        instruments = tags_obj.get("instruments") or []
        all_tags   = [t for t in genres + vartags + instruments if t]

        genre = genres[0] if genres else "Unknown"

        # release_year from releasedate "YYYY-MM-DD"
        release_year = None
        releasedate = raw.get("releasedate", "")
        if releasedate and len(releasedate) >= 4:
            try:
                release_year = int(releasedate[:4])
            except ValueError:
                pass

        is_downloadable = bool(raw.get("audiodownload_allowed", False))
        download_url    = raw.get("audiodownload", "") if is_downloadable else ""
        source_url      = raw.get("shareurl") or f"https://www.jamendo.com/track/{track_id_raw}"
        cover_art_url   = raw.get("album_image") or raw.get("image")

        attribution = f'"{title}" by {artist_name} — {license_url} — {source_url}'

        item: dict = {
            "track_id":         track_id,
            "title":            title,
            "content_type":     "music",
            "artist_id":        artist_id,
            "artist_name":      artist_name,
            "album_id":         album_id,
            "album_title":      album_title,
            "genre":            genre,
            "tags":             all_tags,
            "source_platform":  "jamendo",
            "stream_url":       stream_url,
            "source_url":       source_url,
            "license_type":     license_url,
            "is_streamable":    True,
            "is_downloadable":  is_downloadable,
            "attribution_text": attribution,
            "play_count":       0,
            "dataset_version":  "v1.0.0",
            "health_status":    "active",
            "http_status_code": 200,
            "last_checked_at":  now,
            "added_at":         now,
            "last_updated_at":  now,
        }

        # Sparse fields — omit if None so GSIs stay clean
        if cover_art_url:
            item["cover_art_url"] = cover_art_url
        if release_year:
            item["release_year"] = release_year
        if download_url:
            item["download_url"] = download_url

        duration = raw.get("duration")
        if duration is not None:
            try:
                item["duration_sec"] = Decimal(str(int(duration)))
            except (ValueError, TypeError):
                pass

        position = raw.get("position")
        if position is not None:
            try:
                item["track_number"] = int(position)
            except (ValueError, TypeError):
                pass

        speed = musicinfo.get("speed")
        if speed:
            item["mood"] = speed  # low / medium / high maps well to mood

        return item
