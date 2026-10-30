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
    params = event.get("queryStringParameters") or {}
    query  = (params.get("q") or "").strip().lower()

    if not query:
        return _response(400, {"error": "BAD_REQUEST", "message": "Provide q= parameter"})

    # Scan for active tracks matching artist name
    filter_expr = (
        Attr("health_status").eq("active") &
        Attr("artist_name").contains(query)
    )

    artists: dict[str, dict] = {}
    scan_kwargs = {"FilterExpression": filter_expr}

    try:
        while True:
            resp = _get_table().scan(**scan_kwargs)
            for item in resp.get("Items", []):
                aid  = item.get("artist_id") or item.get("artist_name", "")
                name = item.get("artist_name", "")
                if not aid:
                    continue
                if aid not in artists:
                    artists[aid] = {"artist_id": aid, "artist_name": name, "track_count": 0}
                artists[aid]["track_count"] += 1
            last = resp.get("LastEvaluatedKey")
            if not last:
                break
            scan_kwargs["ExclusiveStartKey"] = last
    except ClientError as e:
        logger.error("artists scan error: %s", e.response["Error"]["Message"])
        return _response(500, {"error": "INTERNAL_ERROR"})

    results = sorted(artists.values(), key=lambda a: (-a["track_count"], a["artist_name"]))

    return _response(200, {"count": len(results), "query": query, "results": results})
