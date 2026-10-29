import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "track_id", "title", "artist_id", "artist_name",
    "album_id", "album_title", "genre", "source_platform",
    "stream_url", "source_url", "license_type",
    "health_status", "added_at", "last_updated_at", "last_checked_at",
    "dataset_version",
]

ALLOWED_PLATFORMS = {"internet_archive", "jamendo", "fma"}
ALLOWED_HEALTH_STATUSES = {"active", "dead_link", "pending_recheck"}


def normalize(item: dict) -> dict | None:
    """
    Validate and coerce a pre-normalized adapter record into the
    final Master Schema shape. Returns None if the record is invalid.
    """
    # Required field check
    for field in REQUIRED_FIELDS:
        if not item.get(field):
            logger.warning("normalize: missing required field '%s' in %s", field, item.get("track_id", "UNKNOWN"))
            return None

    # Platform whitelist
    if item.get("source_platform") not in ALLOWED_PLATFORMS:
        logger.warning("normalize: unknown platform '%s'", item.get("source_platform"))
        return None

    # Health status whitelist
    if item.get("health_status") not in ALLOWED_HEALTH_STATUSES:
        logger.warning("normalize: invalid health_status '%s'", item.get("health_status"))
        return None

    # stream_url must be http(s)
    stream_url = item.get("stream_url", "")
    if not stream_url.startswith(("http://", "https://")):
        logger.warning("normalize: invalid stream_url '%s'", stream_url)
        return None

    # Coerce numeric types to Decimal for DynamoDB compatibility
    item = _coerce_decimals(item)

    # Sanitize string fields — strip whitespace
    for field in ["title", "artist_name", "album_title", "genre"]:
        if isinstance(item.get(field), str):
            item[field] = item[field].strip()

    # Ensure tags is always a list
    if "tags" not in item or item["tags"] is None:
        item["tags"] = []

    # Ensure boolean fields are actual booleans
    item["is_streamable"] = bool(item.get("is_streamable", True))
    item["is_downloadable"] = bool(item.get("is_downloadable", False))

    # Ensure play_count is an int
    item["play_count"] = int(item.get("play_count") or 0)

    return item


def _coerce_decimals(item: dict) -> dict:
    """Convert float values to Decimal for DynamoDB. Operates recursively on dicts."""
    for key, value in item.items():
        if isinstance(value, float):
            try:
                item[key] = Decimal(str(value))
            except InvalidOperation:
                item[key] = None
        elif isinstance(value, dict):
            item[key] = _coerce_decimals(value)
    return item
