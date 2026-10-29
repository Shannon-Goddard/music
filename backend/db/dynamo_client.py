import boto3
import json
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = "music-tracks"
REGION = "us-east-1"

_dynamodb = None


def get_table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=REGION)
    return _dynamodb.Table(TABLE_NAME)


def put_track(item: dict) -> bool:
    try:
        get_table().put_item(Item=item)
        return True
    except ClientError as e:
        logger.error("put_track failed: %s", e.response["Error"]["Message"])
        return False


def get_track(track_id: str) -> dict | None:
    try:
        response = get_table().get_item(Key={"track_id": track_id})
        return response.get("Item")
    except ClientError as e:
        logger.error("get_track failed: %s", e.response["Error"]["Message"])
        return None
