import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key, Attr
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


def _collect_albums(items: list) -> list:
    albums: dict[str, dict] = {}
    for item in items:
        aid   = item.get("album_id") or item.get("album_title", "")
        title = item.get("album_title", "")
        if not aid:
            continue
        if aid not in albums:
            albums[aid] = {
                "album_id":    aid,
                "album_title": title,
                "artist_id":   item.get("artist_id"),
                "artist_name": item.get("artist_name"),
                "cover_art_url": item.get("cover_art_url"),
                "track_count": 0,
            }
        albums[aid]["track_count"] += 1
        # Prefer a non-null cover_art_url
        if not albums[aid]["cover_art_url"] and item.get("cover_art_url"):
            albums[aid]["cover_art_url"] = item["cover_art_url"]
    return sorted(albums.values(), key=lambda a: (-a["track_count"], a["album_title"]))


def handler(event, context):
    params    = event.get("queryStringParameters") or {}
    artist_id = (params.get("artist_id") or "").strip()
    query     = (params.get("q") or "").strip().lower()

    if not artist_id and not query:
        return _response(400, {"error": "BAD_REQUEST", "message": "Provide artist_id= or q= parameter"})

    all_items = []
    scan_kwargs: dict = {}

    try:
        if artist_id:
            # ArtistIndex GSI: hash=artist_id
            query_kwargs = {
                "IndexName": "ArtistIndex",
                "KeyConditionExpression": Key("artist_id").eq(artist_id),
                "FilterExpression": Attr("health_status").eq("active"),
            }
            while True:
                resp = _get_table().query(**query_kwargs)
                all_items.extend(resp.get("Items", []))
                last = resp.get("LastEvaluatedKey")
                if not last:
                    break
                query_kwargs["ExclusiveStartKey"] = last
        else:
            scan_kwargs = {
                "FilterExpression": (
                    Attr("health_status").eq("active") &
                    Attr("album_title").contains(query)
                )
            }
            while True:
                resp = _get_table().scan(**scan_kwargs)
                all_items.extend(resp.get("Items", []))
                last = resp.get("LastEvaluatedKey")
                if not last:
                    break
                scan_kwargs["ExclusiveStartKey"] = last
    except ClientError as e:
        logger.error("albums error: %s", e.response["Error"]["Message"])
        return _response(500, {"error": "INTERNAL_ERROR"})

    results = _collect_albums(all_items)
    return _response(200, {"count": len(results), "query": artist_id or query, "results": results})
