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
# Module-level total cache — survives warm Lambda invocations
_total_active: int | None = None


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


def _get_total_active() -> int:
    """Return total active track count, cached in Lambda memory."""
    global _total_active
    if _total_active is not None:
        return _total_active
    try:
        resp = _get_table().scan(
            FilterExpression=Attr("health_status").eq("active"),
            Select="COUNT",
        )
        _total_active = resp.get("Count", 0)
        # Handle pagination for count
        while resp.get("LastEvaluatedKey"):
            resp = _get_table().scan(
                FilterExpression=Attr("health_status").eq("active"),
                Select="COUNT",
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            _total_active += resp.get("Count", 0)
    except ClientError as e:
        logger.error("count error: %s", e.response["Error"]["Message"])
        _total_active = 0
    return _total_active


def _paginate_scan(filter_expr, offset: int, limit: int) -> tuple[list, int]:
    """
    Scan with filter, skip `offset` matching items, return `limit` items
    and the total matching count. Uses track_id for stable ordering.
    """
    all_items = []
    scan_kwargs = {"FilterExpression": filter_expr}

    while True:
        resp = _get_table().scan(**scan_kwargs)
        all_items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        scan_kwargs["ExclusiveStartKey"] = last

    # Stable sort by track_id so pages never overlap or skip
    all_items.sort(key=lambda x: x.get("track_id", ""))
    total = len(all_items)
    page  = all_items[offset: offset + limit]
    return page, total


def _paginate_query(index: str, key_expr, filter_expr, offset: int, limit: int) -> tuple[list, int]:
    """
    Query a GSI, collect all matching items, sort by track_id, return page + total.
    """
    all_items = []
    query_kwargs = {
        "IndexName": index,
        "KeyConditionExpression": key_expr,
        "FilterExpression": filter_expr,
        "ScanIndexForward": False,
    }

    while True:
        resp = _get_table().query(**query_kwargs)
        all_items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        query_kwargs["ExclusiveStartKey"] = last

    all_items.sort(key=lambda x: x.get("track_id", ""))
    total = len(all_items)
    page  = all_items[offset: offset + limit]
    return page, total


def _lang_filter(lang: str):
    """Return a filter expression for language.
    'eng' matches records with language=eng OR no language field (music is language-agnostic).
    Any other code matches only that language.
    """
    if lang == "eng":
        return Attr("language").eq("eng") | Attr("language").not_exists()
    return Attr("language").eq(lang)


def _search_by_content_type(content_type: str, lang: str, offset: int, limit: int) -> tuple[list, int]:
    try:
        lang_expr = _lang_filter(lang) if lang else None
        base = Attr("health_status").eq("active")
        filter_expr = (base & lang_expr) if lang_expr else base
        return _paginate_query(
            "ContentTypeIndex",
            Key("content_type").eq(content_type),
            filter_expr,
            offset, limit,
        )
    except ClientError as e:
        logger.error("search_by_content_type error: %s", e.response["Error"]["Message"])
        return [], 0


def _search_by_genre(genre: str, lang: str, offset: int, limit: int) -> tuple[list, int]:
    lang_expr = _lang_filter(lang) if lang else None
    base = Attr("health_status").eq("active")
    filter_expr = (base & lang_expr) if lang_expr else base
    try:
        items, total = _paginate_query(
            "GenreIndex",
            Key("genre").eq(genre),
            filter_expr,
            offset, limit,
        )
        if total:
            return items, total
    except ClientError as e:
        logger.error("search_by_genre GSI error: %s", e.response["Error"]["Message"])

    try:
        return _paginate_scan(
            filter_expr & Attr("genre").contains(genre),
            offset, limit,
        )
    except ClientError as e:
        logger.error("search_by_genre scan error: %s", e.response["Error"]["Message"])
        return [], 0


def _search_by_text(query: str, lang: str, offset: int, limit: int) -> tuple[list, int]:
    q = query.lower()
    lang_expr = _lang_filter(lang) if lang else None
    base = Attr("health_status").eq("active")
    filter_expr = (base & lang_expr) if lang_expr else base
    try:
        return _paginate_scan(
            filter_expr & (
                Attr("title").contains(query)       |
                Attr("artist_name").contains(query) |
                Attr("album_title").contains(query) |
                Attr("title").contains(q)           |
                Attr("artist_name").contains(q)     |
                Attr("album_title").contains(q)
            ),
            offset, limit,
        )
    except ClientError as e:
        logger.error("search_by_text error: %s", e.response["Error"]["Message"])
        return [], 0


def _format_track(item: dict) -> dict:
    return {
        "content_type":    item.get("content_type", "other"),
        "track_id":        item.get("track_id"),
        "title":           item.get("title"),
        "artist_id":       item.get("artist_id"),
        "artist_name":     item.get("artist_name"),
        "album_id":        item.get("album_id"),
        "album_title":     item.get("album_title"),
        "genre":           item.get("genre"),
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
    params       = event.get("queryStringParameters") or {}
    query        = (params.get("q")    or "").strip()
    genre        = (params.get("genre") or "").strip()
    content_type = (params.get("type") or "").strip()
    # lang= defaults to 'eng' (English + language-agnostic music)
    # pass lang=all to disable the filter
    lang_param   = (params.get("lang") or "eng").strip()
    lang         = "" if lang_param == "all" else lang_param

    try:
        limit  = min(int(params.get("limit",  20)), 100)
        offset = max(int(params.get("offset",  0)),   0)
    except (ValueError, TypeError):
        limit, offset = 20, 0

    if not query and not genre and not content_type:
        return _response(400, {"error": "BAD_REQUEST", "message": "Provide q=, genre=, or type= parameter"})

    if content_type:
        items, total = _search_by_content_type(content_type, lang, offset, limit)
    elif genre:
        items, total = _search_by_genre(genre, lang, offset, limit)
    else:
        items, total = _search_by_text(query, lang, offset, limit)

    tracks = [_format_track(item) for item in items]

    return _response(200, {
        "count":   len(tracks),
        "total":   total,
        "offset":  offset,
        "query":   query or genre or content_type,
        "results": tracks,
    })
