"""
Ingest ccMixter CC-licensed tracks into DynamoDB.
Run: python tests/test_ingest_ccmixter.py
"""
import logging
import sys
import os

import boto3
from boto3.dynamodb.conditions import Attr

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.ingestion.ccmixter_adapter import CCMixterAdapter
from backend.ingestion import normalizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TABLE_NAME = "music-tracks"
MAX_PAGES  = 400   # 400 × 50 = up to 20,000 tracks
REGION     = "us-east-1"


def get_table():
    return boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)


def wipe_ccmixter(table):
    logger.info("Wiping existing ccMixter records...")
    deleted = 0
    scan_kwargs = {"FilterExpression": Attr("source_platform").eq("ccmixter")}
    while True:
        resp = table.scan(**scan_kwargs)
        items = resp.get("Items", [])
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"track_id": item["track_id"]})
                deleted += 1
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        scan_kwargs["ExclusiveStartKey"] = last
    logger.info("Wiped %d existing ccMixter records", deleted)


def run():
    table   = get_table()
    adapter = CCMixterAdapter()

    wipe_ccmixter(table)

    ingested = 0
    no_cc    = 0
    no_mp3   = 0
    skipped  = 0
    errors   = 0
    content_type_counts: dict[str, int] = {}
    consecutive_empty = 0

    for page in range(MAX_PAGES):
        raw_records = adapter.fetch(page)

        if not raw_records:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                logger.info("3 consecutive empty pages — done at page %d", page)
                break
            continue
        consecutive_empty = 0

        with table.batch_writer() as batch:
            for raw in raw_records:
                normalized = adapter.normalize(raw)
                if normalized is None:
                    # Distinguish no-CC from no-MP3
                    if "creativecommons.org" not in (raw.get("license_url") or ""):
                        no_cc += 1
                    else:
                        no_mp3 += 1
                    continue

                validated = normalizer.normalize(normalized)
                if validated is None:
                    skipped += 1
                    continue

                try:
                    batch.put_item(Item=validated)
                    ct = validated.get("content_type", "other")
                    content_type_counts[ct] = content_type_counts.get(ct, 0) + 1
                    ingested += 1
                except Exception as e:
                    logger.error("Write error: %s | %s", e, validated.get("track_id"))
                    errors += 1

        if ingested % 1000 == 0 and ingested > 0:
            logger.info("  %d ingested so far...", ingested)

        logger.info("Page %d — ingested: %d, no_cc: %d, no_mp3: %d, skipped: %d",
                    page, ingested, no_cc, no_mp3, skipped)

    logger.info("\n=== ccMixter Ingestion Complete ===")
    logger.info("Total ingested  : %d", ingested)
    logger.info("No CC skipped   : %d", no_cc)
    logger.info("No MP3 skipped  : %d", no_mp3)
    logger.info("Invalid skipped : %d", skipped)
    logger.info("Errors          : %d", errors)
    logger.info("By content_type : %s", content_type_counts)


if __name__ == "__main__":
    run()
