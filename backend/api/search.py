import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "music-tracks")
REGION = os.environ.get("AWS_REGION", "us-east-1")

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


def _search_by_genre(genre: str, limit: int) -> list[dict]:
    try:
        response = _get_table().query(
            IndexName="GenreIndex",
            KeyConditionExpression=Key("genre").eq(genre),
            FilterExpression=Attr("health_status").eq("active"),
            Limit=limit,
            ScanIndexForward=False,  # newest first
        )
        return response.get("Items", [])
    except ClientError as e:
        logger.error("search_by_genre error: %s", e.response["Error"]["Message"])
        return []


def _search_by_text(query: str, limit: int) -> list[dict]:
    """
    Full-text style search via DynamoDB scan with filter expressions.
    Searches title, artist_name, and album_title.
    Note: for production scale this should be replaced with OpenSearch.
    """
    q = query.lower()
    try:
        response = _get_table().scan(
            FilterExpression=(
                Attr("health_status").eq("active") &
                (
                    Attr("title").contains(query) |
                    Attr("artist_name").contains(query) |
                    Attr("album_title").contains(query) |
                    Attr("title").contains(q) |
                    Attr("artist_name").contains(q) |
                    Attr("album_title").contains(q)
                )
            ),
            Limit=limit,
        )
        return response.get("Items", [])
    except ClientError as e:
        logger.error("search_by_text error: %s", e.response["Error"]["Message"])
        return []


def _format_track(item: dict) -> dict:
    """Return only the fields the frontend needs."""
    return {
        "track_id": item.get("track_id"),
        "title": item.get("title"),
        "artist_id": item.get("artist_id"),
        "artist_name": item.get("artist_name"),
        "album_id": item.get("album_id"),
        "album_title": item.get("album_title"),
        "genre": item.get("genre"),
        "tags": item.get("tags", []),
        "duration_sec": item.get("duration_sec"),
        "cover_art_url": item.get("cover_art_url"),
        "stream_url": item.get("stream_url"),
        "source_url": item.get("source_url"),
        "license_type": item.get("license_type"),
        "is_downloadable": item.get("is_downloadable", False),
        "attribution_text": item.get("attribution_text"),
    }


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    query = (params.get("q") or "").strip()
    genre = (params.get("genre") or "").strip()

    try:
        limit = min(int(params.get("limit", 20)), 100)
    except (ValueError, TypeError):
        limit = 20

    if not query and not genre:
        return _response(400, {"error": "BAD_REQUEST", "message": "Provide q= or genre= parameter"})

    if genre:
        items = _search_by_genre(genre, limit)
    else:
        items = _search_by_text(query, limit)

    tracks = [_format_track(item) for item in items]

    return _response(200, {
        "count": len(tracks),
        "query": query or genre,
        "results": tracks,
    })
