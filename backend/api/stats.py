import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "music-tracks")
REGION     = os.environ.get("AWS_REGION", "us-east-1")

_table = None
_cache: dict | None = None  # warm-Lambda cache, refreshes on cold start


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


def _build_stats() -> dict:
    """Full-table scan to aggregate stats. Cached in Lambda memory."""
    total = 0
    by_platform: dict[str, int] = {}
    by_genre: dict[str, int] = {}
    by_type: dict[str, int] = {}

    scan_kwargs: dict = {
        "FilterExpression": Attr("health_status").eq("active"),
        "ProjectionExpression": "source_platform, genre, content_type",
    }

    while True:
        resp = _get_table().scan(**scan_kwargs)
        for item in resp.get("Items", []):
            total += 1
            p = item.get("source_platform") or "unknown"
            g = item.get("genre") or "unknown"
            t = item.get("content_type") or "other"
            by_platform[p] = by_platform.get(p, 0) + 1
            by_genre[g]     = by_genre.get(g, 0) + 1
            by_type[t]      = by_type.get(t, 0) + 1
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        scan_kwargs["ExclusiveStartKey"] = last

    # Top 20 genres by count
    top_genres = sorted(by_genre.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "total_tracks": total,
        "by_platform":  dict(sorted(by_platform.items(), key=lambda x: x[1], reverse=True)),
        "by_type":      dict(sorted(by_type.items(),     key=lambda x: x[1], reverse=True)),
        "top_genres":   [{"genre": g, "count": c} for g, c in top_genres],
    }


def handler(event, context):
    global _cache
    if _cache is None:
        try:
            _cache = _build_stats()
        except ClientError as e:
            logger.error("stats error: %s", e.response["Error"]["Message"])
            return _response(500, {"error": "INTERNAL_ERROR"})

    return _response(200, _cache)
