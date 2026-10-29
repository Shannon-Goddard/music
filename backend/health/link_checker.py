import logging
import time
from datetime import datetime, timezone

import boto3
import requests
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = "music-tracks"
REGION = "us-east-1"

# Retry backoff intervals in seconds
RETRY_DELAYS = [5, 30, 120]

# HTTP codes that confirm a dead link — no retry
DEAD_CODES = {404, 410, 403}

# HTTP codes that confirm the link is alive
ALIVE_CODES = {200, 301, 302, 206}

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
    return _table


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _head_request(url: str) -> int | None:
    """
    Send a HEAD request with exponential backoff on timeout / 5xx.
    Returns the final HTTP status code, or None if all retries exhausted.
    """
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            logger.info("link_checker: retry %d — waiting %ds before re-checking %s", attempt, delay, url)
            time.sleep(delay)
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            code = response.status_code
            if code in DEAD_CODES:
                return code
            if code >= 500:
                logger.warning("link_checker: %d from %s — will retry", code, url)
                continue
            return code
        except requests.Timeout:
            logger.warning("link_checker: timeout on %s (attempt %d)", url, attempt + 1)
        except requests.RequestException as e:
            logger.warning("link_checker: request error on %s: %s", url, e)

    return None


def _update_track(track_id: str, status: str, http_code: int | None):
    now = _now()
    update_expr = "SET health_status = :s, last_checked_at = :t, last_updated_at = :t"
    expr_values = {":s": status, ":t": now}

    if http_code is not None:
        update_expr += ", http_status_code = :c"
        expr_values[":c"] = http_code

    try:
        _get_table().update_item(
            Key={"track_id": track_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
        logger.info("link_checker: %s → %s (HTTP %s)", track_id, status, http_code)
    except ClientError as e:
        logger.error("link_checker: update failed for %s: %s", track_id, e.response["Error"]["Message"])


def _fetch_active_tracks(limit: int = 100) -> list[dict]:
    """
    Query HealthIndex for active tracks sorted by last_checked_at ASC
    so the oldest-checked tracks are always processed first.
    """
    try:
        response = _get_table().query(
            IndexName="HealthIndex",
            KeyConditionExpression=Key("health_status").eq("active"),
            ScanIndexForward=True,  # ASC — oldest checked first
            Limit=limit,
            ProjectionExpression="track_id, stream_url, last_checked_at",
        )
        return response.get("Items", [])
    except ClientError as e:
        logger.error("link_checker: failed to query HealthIndex: %s", e.response["Error"]["Message"])
        return []


def run(limit: int = 100) -> dict:
    """
    Main entry point. Checks up to `limit` active tracks.
    Returns a summary dict for logging / Lambda response.
    """
    tracks = _fetch_active_tracks(limit)
    logger.info("link_checker: checking %d tracks", len(tracks))

    results = {"alive": 0, "dead": 0, "pending_recheck": 0, "errors": 0}

    for track in tracks:
        track_id = track["track_id"]
        stream_url = track.get("stream_url", "")

        if not stream_url:
            logger.warning("link_checker: no stream_url for %s — marking pending_recheck", track_id)
            _update_track(track_id, "pending_recheck", None)
            results["errors"] += 1
            continue

        code = _head_request(stream_url)

        if code in ALIVE_CODES:
            _update_track(track_id, "active", code)
            results["alive"] += 1
        elif code in DEAD_CODES:
            _update_track(track_id, "dead_link", code)
            results["dead"] += 1
        else:
            # None (all retries exhausted) or unexpected code
            _update_track(track_id, "pending_recheck", code)
            results["pending_recheck"] += 1

    logger.info("link_checker: complete — %s", results)
    return results
