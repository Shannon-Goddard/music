import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "music-tracks")
REGION     = os.environ.get("AWS_REGION", "us-east-1")

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
    return _table


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "*"),
        },
        "body": json.dumps(body, default=str),
    }


def handler(event, context):
    # track_id comes from path parameter /tracks/{id}
    path_params = event.get("pathParameters") or {}
    track_id    = (path_params.get("id") or "").strip()

    if not track_id:
        return _response(400, {"error": "BAD_REQUEST", "message": "Missing track id"})

    try:
        resp = _get_table().get_item(Key={"track_id": track_id})
    except ClientError as e:
        logger.error("get_item error: %s", e.response["Error"]["Message"])
        return _response(500, {"error": "INTERNAL_ERROR"})

    item = resp.get("Item")
    if not item:
        return _response(404, {"error": "NOT_FOUND", "message": f"Track {track_id} not found"})

    return _response(200, {
        "track_id":               item.get("track_id"),
        "title":                  item.get("title"),
        "artist_id":              item.get("artist_id"),
        "artist_name":            item.get("artist_name"),
        "album_id":               item.get("album_id"),
        "album_title":            item.get("album_title"),
        "genre":                  item.get("genre"),
        "tags":                   item.get("tags", []),
        "content_type":           item.get("content_type", "other"),
        "duration_sec":           item.get("duration_sec"),
        "cover_art_url":          item.get("cover_art_url"),
        "stream_url":             item.get("stream_url"),
        "source_url":             item.get("source_url"),
        "license_type":           item.get("license_type"),
        "is_downloadable":        item.get("is_downloadable", False),
        "attribution_text":       item.get("attribution_text"),
        "language":               item.get("language"),
        "source_platform":        item.get("source_platform"),
        "ia_collection":          item.get("ia_collection"),
        "release_year":           item.get("release_year"),
        "musicbrainz_artist_id":  item.get("musicbrainz_artist_id"),
        "musicbrainz_recording_id": item.get("musicbrainz_recording_id"),
        "mb_tags":                item.get("mb_tags", []),
        "health_status":          item.get("health_status"),
        "added_at":               item.get("added_at"),
    })
