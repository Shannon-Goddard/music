import json
import logging
import os
import random

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "music-tracks")
REGION     = os.environ.get("AWS_REGION", "us-east-1")
RADIO_SIZE = 50

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


def _fetch_by_genre(genre: str) -> list:
    """Collect all active tracks for a genre via GenreIndex."""
    items = []
    kwargs = {
        "IndexName": "GenreIndex",
        "KeyConditionExpression": Key("genre").eq(genre),
        "FilterExpression": Attr("health_status").eq("active"),
    }
    while True:
        resp = _get_table().query(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return items


def _fetch_random_scan(limit: int) -> list:
    """
    Reservoir-sample `limit` active tracks from a full scan.
    Used when no genre is specified.
    """
    reservoir = []
    count = 0
    kwargs = {
        "FilterExpression": Attr("health_status").eq("active"),
        "ProjectionExpression":
            "track_id, title, artist_name, album_title, genre, "
            "duration_sec, cover_art_url, stream_url, source_url, "
            "license_type, is_downloadable, attribution_text, "
            "language, source_platform, content_type, tags",
    }
    while True:
        resp = _get_table().scan(**kwargs)
        for item in resp.get("Items", []):
            count += 1
            if len(reservoir) < limit:
                reservoir.append(item)
            else:
                j = random.randint(0, count - 1)
                if j < limit:
                    reservoir[j] = item
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return reservoir


def _format(item: dict) -> dict:
    return {
        "track_id":        item.get("track_id"),
        "title":           item.get("title"),
        "artist_name":     item.get("artist_name"),
        "album_title":     item.get("album_title"),
        "genre":           item.get("genre"),
        "content_type":    item.get("content_type", "other"),
        "tags":            item.get("tags", []),
        "duration_sec":    item.get("duration_sec"),
        "cover_art_url":   item.get("cover_art_url"),
        "stream_url":      item.get("stream_url"),
        "source_url":      item.get("source_url"),
        "license_type":    item.get("license_type"),
        "is_downloadable": item.get("is_downloadable", False),
        "attribution_text":item.get("attribution_text"),
        "language":        item.get("language"),
        "source_platform": item.get("source_platform"),
    }


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    genre  = (params.get("genre") or "").strip().lower()

    try:
        limit = min(int(params.get("limit", RADIO_SIZE)), 100)
    except (ValueError, TypeError):
        limit = RADIO_SIZE

    try:
        if genre:
            # Capitalise to match stored values (e.g. "jazz" → "Jazz")
            genre_key = genre.capitalize()
            items = _fetch_by_genre(genre_key)
            if not items:
                # Fallback: try exact case as supplied
                items = _fetch_by_genre(genre)
        else:
            return _response(400, {"error": "BAD_REQUEST", "message": "Provide genre= parameter"})
    except ClientError as e:
        logger.error("radio fetch error: %s", e.response["Error"]["Message"])
        return _response(500, {"error": "INTERNAL_ERROR"})

    if not items:
        return _response(404, {"error": "NOT_FOUND", "message": f"No tracks found for genre '{genre}'"})

    sample = random.sample(items, min(limit, len(items)))
    tracks = [_format(t) for t in sample]

    return _response(200, {
        "genre":  genre,
        "count":  len(tracks),
        "tracks": tracks,
    })
