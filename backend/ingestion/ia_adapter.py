import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)

IA_SEARCH_URL   = "https://archive.org/advancedsearch.php"
IA_METADATA_URL = "https://archive.org/metadata"
PAGE_SIZE       = 50
FETCH_WORKERS   = 10   # parallel metadata + HEAD checks per page

# Only ingest openly licensed audio
ALLOWED_LICENSES = ("creativecommons", "publicdomain")

# Ordered: first match wins. More specific genres before broader ones.
_GENRE_MAP = [
    ("metal",        {"metal", "heavy metal", "death metal", "black metal", "doom metal",
                      "thrash", "thrash metal", "grindcore", "hardcore", "extreme metal",
                      "progressive metal", "industrial metal", "sludge", "doom",
                      "raw black metal", "blackened", "deathcore", "metalcore",
                      "speed metal", "nu metal"}),
    ("industrial",   {"industrial", "power electronics", "ebm", "rhythmic noise",
                      "industrial music", "industrial noise", "post-industrial"}),
    ("hip-hop",      {"rap", "hip - hop", "hip-hop", "hiphop", "hip hop",
                      "underground rap", "underground hip - hop", "spanish rap",
                      "alternative rap", "latin rap", "emo rap", "instrumental hip-hop",
                      "boom bap", "trap", "lo-fi", "lofi"}),
    ("experimental", {"experimental", "experimental music", "noise", "harsh noise",
                      "avant garde", "avantgarde", "avant-garde", "musique concrete",
                      "sound art", "electroacoustic", "abstract", "plunderphonics",
                      "glitch", "microsound", "acousmatic", "sound collage"}),
    ("electronic",   {"electronic", "electronica", "idm", "techno", "house", "deep house",
                      "minimal techno", "acid", "acid techno", "electro", "vaporwave",
                      "synthpop", "synthwave", "darkwave", "chiptune", "8bit",
                      "breakcore", "dubstep", "drum & bass", "drumnbass", "breakbeat",
                      "trance", "psytrance", "ambient techno", "dark electronic"}),
    ("ambient",      {"ambient", "dark ambient", "drone", "soundscape", "soundscapes",
                      "drone ambient", "space ambient", "ritual ambient", "noise ambient",
                      "atmospheric", "meditation", "new age", "downtempo",
                      "chillout", "chill out", "chill-out"}),
    ("jazz",         {"jazz", "free jazz", "jazz+funk", "nujazz", "swing", "big band",
                      "bebop", "smooth jazz", "acid jazz", "improvisation",
                      "free improvisation", "improv"}),
    ("classical",    {"classical", "classical music", "orchestral", "opera", "operetta",
                      "choral", "symphony", "neoclassical", "contemporary classical",
                      "20th century classical", "modern classical", "chamber",
                      "piano", "organ", "violin", "baroque"}),
    ("folk",         {"folk", "folk music", "folk dance", "experimental folk",
                      "singer-songwriter", "singer songwriter", "acoustic", "country",
                      "bluegrass", "celtic", "traditional", "oldtime", "old time",
                      "neofolk", "americana", "alt-country"}),
    ("blues",        {"blues", "delta blues", "chicago blues", "electric blues",
                      "rhythm and blues", "rhythm & blues"}),
    ("punk",         {"punk", "punk rock", "post-punk", "post punk", "hardcore punk",
                      "anarcho punk", "oi", "street punk"}),
    ("reggae",       {"reggae", "dub", "ska", "dancehall", "roots reggae", "rocksteady"}),
    ("soul",         {"soul", "soul music", "motown", "funk", "neo soul"}),
    ("rock",         {"rock", "classic rock", "alternative", "indie rock", "indie",
                      "garage rock", "psychedelic rock", "progressive rock", "space rock",
                      "post-rock", "post rock", "krautrock", "kraut rock", "noise rock",
                      "art rock", "alternative rock", "rock and roll", "rock n roll",
                      "rock & roll", "rockabilly", "stoner rock", "shoegaze", "grunge"}),
    ("pop",          {"pop", "pop music", "indie pop", "dream pop", "chamber pop",
                      "baroque pop", "art pop"}),
]

_TAG_TO_GENRE: dict[str, str] = {
    t.lower(): genre for genre, tags in _GENRE_MAP for t in tags
}


def _resolve_genre(subjects: list) -> str:
    """Map raw IA subject tags to a clean genre key, or return 'Unknown'."""
    for tag in subjects:
        mapped = _TAG_TO_GENRE.get(tag.lower().strip())
        if mapped:
            return mapped
    return "Unknown"

# Targeted collection queries
IA_COLLECTIONS = {
    "netlabels": (
        "mediatype:audio AND collection:netlabels AND "
        "licenseurl:(*creativecommons* OR *publicdomain*)"
    ),
    "78rpm": (
        "mediatype:audio AND collection:78rpm AND "
        "licenseurl:(*creativecommons* OR *publicdomain*)"
    ),
    # 3M+ items — CC-licensed by definition, all content types welcome
    "opensource_audio": (
        "mediatype:audio AND collection:opensource_audio AND "
        "licenseurl:(*creativecommons* OR *publicdomain*)"
    ),
    # 535k music-focused items
    "audio_music": (
        "mediatype:audio AND collection:audio_music AND "
        "licenseurl:(*creativecommons* OR *publicdomain*)"
    ),
    # 187k digitized 78rpm + shellac records, pre-1928 public domain by US law
    # No licenseurl field on these items — assigned at normalize time
    "georgeblood": (
        "mediatype:audio AND collection:georgeblood"
    ),
    # 75k audiobooks + poetry
    "audio_bookspoetry": (
        "mediatype:audio AND collection:audio_bookspoetry AND "
        "licenseurl:(*creativecommons* OR *publicdomain*)"
    ),
    # 21k LibriVox public domain audiobooks
    "librivoxaudio": (
        "mediatype:audio AND collection:librivoxaudio AND "
        "licenseurl:(*creativecommons* OR *publicdomain*)"
    ),
}

# Keywords used to classify content_type from subject/title
_PODCAST_WORDS   = {"podcast", "episode", "show", "radio show", "broadcast"}
_INTERVIEW_WORDS = {"interview", "conversation", "talk", "discussion", "q&a"}
_LECTURE_WORDS   = {"lecture", "sermon", "speech", "talk", "lesson", "class", "course", "seminar"}
_AUDIOBOOK_WORDS = {"audiobook", "audio book", "reading", "narration", "story", "chapter"}
_MUSIC_WORDS     = {"music", "song", "album", "instrumental", "jazz", "rock", "classical",
                    "folk", "electronic", "blues", "ambient", "pop", "hip-hop", "soundtrack",
                    "band", "orchestra", "concert", "live", "single", "ep", "lp"}

# Normalize the messy IA language field to ISO 639-2 three-letter codes
_LANG_MAP = {
    # English variants
    "english": "eng", "en": "eng", "eng": "eng",
    # Spanish
    "spanish": "spa", "español": "spa", "es": "spa", "spa": "spa",
    # French
    "french": "fra", "français": "fra", "fr": "fra", "fra": "fra", "fre": "fra",
    # German
    "german": "deu", "deutsch": "deu", "de": "deu", "deu": "deu", "ger": "deu",
    # Italian
    "italian": "ita", "italiano": "ita", "it": "ita", "ita": "ita",
    # Portuguese
    "portuguese": "por", "português": "por", "pt": "por", "por": "por",
    # Russian
    "russian": "rus", "ru": "rus", "rus": "rus",
    # Japanese
    "japanese": "jpn", "ja": "jpn", "jpn": "jpn",
    # Chinese
    "chinese": "zho", "zh": "zho", "zho": "zho", "chi": "zho",
    # Arabic
    "arabic": "ara", "ar": "ara", "ara": "ara",
    # Dutch
    "dutch": "nld", "nl": "nld", "nld": "nld", "dut": "nld",
    # Greek
    "greek": "ell", "el": "ell", "ell": "ell", "gre": "ell",
    # Latin
    "latin": "lat", "la": "lat", "lat": "lat",
    # Yiddish
    "yiddish": "yid", "yid": "yid",
    # Danish
    "danish": "dan", "da": "dan", "dan": "dan",
    # Swedish
    "swedish": "swe", "sv": "swe", "swe": "swe",
    # Norwegian
    "norwegian": "nor", "no": "nor", "nor": "nor",
    # Finnish
    "finnish": "fin", "fi": "fin", "fin": "fin",
    # Polish
    "polish": "pol", "pl": "pol", "pol": "pol",
    # Czech
    "czech": "ces", "cs": "ces", "ces": "ces", "cze": "ces",
    # Hungarian
    "hungarian": "hun", "hu": "hun", "hun": "hun",
    # Croatian
    "croatian": "hrv", "hr": "hrv", "hrv": "hrv",
    # Swiss (ambiguous — treat as German)
    "swiss": "deu",
}


def _normalize_language(raw_lang) -> str | None:
    """Return ISO 639-2 code or None if unknown/missing."""
    if not raw_lang:
        return None
    val = str(raw_lang).strip().lower()
    return _LANG_MAP.get(val)


class IAAdapter(BaseAdapter):

    def fetch(self, page: int = 0, collection: str = "netlabels") -> list[dict]:
        query = IA_COLLECTIONS.get(collection, IA_COLLECTIONS["netlabels"])
        params = {
            "q": query,
            "fl[]": ["identifier", "title", "creator", "subject",
                     "year", "licenseurl", "language"],
            "rows": PAGE_SIZE,
            "page": page + 1,
            "sort[]": "addeddate desc",
            "output": "json",
        }
        try:
            response = requests.get(IA_SEARCH_URL, params=params, timeout=15)
            response.raise_for_status()
            docs = response.json().get("response", {}).get("docs", [])
            logger.info("IA [%s] page %d: fetched %d records", collection, page, len(docs))
            return docs
        except requests.RequestException as e:
            logger.error("IA fetch error on page %d: %s", page, e)
            return []

    def normalize_batch(self, raws: list[dict], collection: str = "netlabels") -> list[dict]:
        """Normalize a full page in parallel — ~10x faster than serial."""
        results = []
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            futures = {pool.submit(self.normalize, raw, collection): raw for raw in raws}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        return results

    def normalize(self, raw: dict, collection: str = "netlabels") -> dict | None:
        identifier = raw.get("identifier")
        if not identifier:
            return None

        # Verify license
        license_url = raw.get("licenseurl", "")
        if not license_url and collection == "georgeblood":
            license_url = "https://creativecommons.org/publicdomain/mark/1.0/"
        if not any(allowed in license_url.lower() for allowed in ALLOWED_LICENSES):
            return None

        # Fetch full item metadata
        meta = self._fetch_metadata(identifier)
        if not meta:
            return None

        audio_file = self._pick_audio(meta.get("files", []))
        if not audio_file:
            return None

        stream_url = f"https://archive.org/download/{identifier}/{audio_file['name']}"

        if not self._is_publicly_streamable(stream_url):
            logger.info("IA: skipping non-public stream for %s", identifier)
            return None

        source_url = f"https://archive.org/details/{identifier}"
        track_id   = f"TRK-IA-{identifier}"
        now        = datetime.now(timezone.utc).isoformat()

        title = raw.get("title") or audio_file.get("title") or identifier
        creator = raw.get("creator") or "Unknown Artist"
        if isinstance(creator, list):
            creator = creator[0] if creator else "Unknown Artist"
        creator   = str(creator).strip() or "Unknown Artist"
        artist_id = f"ART-IA-{hashlib.md5(creator.encode()).hexdigest()[:8]}"

        subjects     = self._to_list(raw.get("subject"))
        content_type = self._detect_content_type(subjects, title)
        language     = _normalize_language(raw.get("language"))

        item = {
            "track_id":         track_id,
            "title":            title,
            "content_type":     content_type,
            "release_year":     self._to_int(raw.get("year")),
            "artist_id":        artist_id,
            "artist_name":      creator,
            "album_id":         f"ALB-IA-{identifier}",
            "album_title":      raw.get("title") or identifier,
            "genre":            _resolve_genre(subjects),
            "tags":             subjects,
            "source_platform":  "internet_archive",
            "stream_url":       stream_url,
            "source_url":       source_url,
            "format":           audio_file.get("name", "").rsplit(".", 1)[-1].lower(),
            "audio_hash_md5":   audio_file.get("md5") or "",
            "license_type":     license_url,
            "is_streamable":    True,
            "is_downloadable":  True,
            "attribution_text": f'"{title}" by {creator} — {license_url} — {source_url}',
            "play_count":       0,
            "ia_collection":    collection,
            "dataset_version":  "v1.0.0",
            "health_status":    "active",
            "http_status_code": 200,
            "last_checked_at":  now,
            "added_at":         now,
            "last_updated_at":  now,
        }

        if language:
            item["language"] = language

        duration = self._to_decimal(audio_file.get("length"))
        if duration is not None:
            item["duration_sec"] = duration

        bitrate = self._to_int(audio_file.get("bitrate"))
        if bitrate is not None:
            item["bitrate_kbps"] = bitrate

        track_number = self._to_int(audio_file.get("track"))
        if track_number is not None:
            item["track_number"] = track_number

        cover = self._cover_art_url(identifier, meta.get("files", []))
        if cover:
            item["cover_art_url"] = cover

        return item

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_content_type(self, subjects: list, title: str) -> str:
        tokens = {w.lower() for s in subjects for w in s.replace("-", " ").split()}
        tokens |= {w.lower() for w in title.replace("-", " ").split()}
        if tokens & _LECTURE_WORDS:   return "lecture"
        if tokens & _INTERVIEW_WORDS: return "interview"
        if tokens & _PODCAST_WORDS:   return "podcast"
        if tokens & _AUDIOBOOK_WORDS: return "audiobook"
        if tokens & _MUSIC_WORDS:     return "music"
        return "other"

    def _is_publicly_streamable(self, url: str) -> bool:
        try:
            r = requests.head(url, timeout=8, allow_redirects=True)
            return r.status_code in {200, 206, 301, 302}
        except requests.RequestException:
            return False

    def _fetch_metadata(self, identifier: str) -> dict | None:
        try:
            r = requests.get(f"{IA_METADATA_URL}/{identifier}", timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.error("IA metadata fetch failed for %s: %s", identifier, e)
            return None

    def _pick_audio(self, files: list[dict]) -> dict | None:
        """Prefer MP3, fall back to WAV then M4A."""
        def _ext(f): return f.get("name", "").lower()
        mp3s = [f for f in files if _ext(f).endswith(".mp3")]
        if mp3s:
            mp3s.sort(key=lambda f: self._to_int(f.get("bitrate")) or 0, reverse=True)
            return mp3s[0]
        wavs = [f for f in files if _ext(f).endswith(".wav")]
        if wavs:
            return wavs[0]
        m4as = [f for f in files if _ext(f).endswith((".m4a", ".mp4"))]
        if m4as:
            return m4as[0]
        return None

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
            return Decimal(str(float(value))).quantize(Decimal("0.01"))
        except (TypeError, ValueError, InvalidOperation):
            return None

    def _to_int(self, value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
