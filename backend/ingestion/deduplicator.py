import logging

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = "music-tracks"
REGION = "us-east-1"

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
    return _table


def is_duplicate(track_id: str, audio_hash_md5: str | None) -> bool:
    """
    Returns True if the track already exists in DynamoDB.
    Checks track_id first (fast, single key lookup).
    Falls back to audio_hash_md5 scan if track_id is not found but hash is provided.
    """
    # Primary check: track_id
    try:
        response = _get_table().get_item(
            Key={"track_id": track_id},
            ProjectionExpression="track_id",
        )
        if response.get("Item"):
            logger.debug("dedup: track_id '%s' already exists — skipping", track_id)
            return True
    except ClientError as e:
        logger.error("dedup: get_item error for '%s': %s", track_id, e.response["Error"]["Message"])
        return False

    # Secondary check: MD5 hash (catches re-ingested tracks with new identifiers)
    if audio_hash_md5:
        try:
            response = _get_table().scan(
                FilterExpression=Attr("audio_hash_md5").eq(audio_hash_md5),
                ProjectionExpression="track_id",
                Limit=1,
            )
            if response.get("Items"):
                logger.debug("dedup: md5 '%s' already exists — skipping", audio_hash_md5)
                return True
        except ClientError as e:
            logger.error("dedup: scan error for md5 '%s': %s", audio_hash_md5, e.response["Error"]["Message"])

    return False
