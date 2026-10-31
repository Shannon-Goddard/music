"""
Ingest Jamendo CC-licensed tracks into DynamoDB.
Sweeps all genre tags to maximize coverage, deduplicates by track_id.
Run from repo root: python tests/test_ingest_jamendo.py
"""
import logging
import sys
import os

import boto3
from boto3.dynamodb.conditions import Attr

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.ingestion.jamendo_adapter import JamendoAdapter, JAMENDO_TAGS
from backend.ingestion import normalizer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TABLE_NAME = "music-tracks"
MAX_PAGES  = 10_000  # effectively unlimited — loop breaks on empty page
REGION     = "us-east-1"


def get_table():
    return boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)


def wipe_jamendo(table):
    logger.info("Wiping existing Jamendo records...")
    deleted = 0
    scan_kwargs = {"FilterExpression": Attr("source_platform").eq("jamendo")}
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
    logger.info("Wiped %d existing Jamendo records", deleted)


def run():
    table   = get_table()
    adapter = JamendoAdapter()

    wipe_jamendo(table)

    seen_ids: set[str] = set()   # deduplicate across tag sweeps
    ingested = 0
    dupes    = 0
    no_cc    = 0
    skipped  = 0
    errors   = 0
    content_type_counts: dict[str, int] = {}

    for tag in JAMENDO_TAGS:
        logger.info("--- Sweeping tag: %s ---", tag)
        tag_ingested = 0

        for page in range(MAX_PAGES):  # breaks early on empty page
            raw_records = adapter.fetch(page, tag=tag)
            if not raw_records:
                logger.info("  [%s] empty page %d — moving to next tag", tag, page)
                break

            with table.batch_writer() as batch:
                for raw in raw_records:
                    normalized = adapter.normalize(raw)
                    if normalized is None:
                        no_cc += 1
                        continue

                    tid = normalized["track_id"]
                    if tid in seen_ids:
                        dupes += 1
                        continue
                    seen_ids.add(tid)

                    validated = normalizer.normalize(normalized)
                    if validated is None:
                        skipped += 1
                        continue

                    try:
                        batch.put_item(Item=validated)
                        ct = validated.get("content_type", "other")
                        content_type_counts[ct] = content_type_counts.get(ct, 0) + 1
                        ingested += 1
                        tag_ingested += 1
                    except Exception as e:
                        logger.error("Write error: %s | %s", e, validated.get("track_id"))
                        errors += 1

        logger.info("  [%s] done — %d new tracks", tag, tag_ingested)

    logger.info("\n=== Jamendo Ingestion Complete ===")
    logger.info("Total ingested  : %d", ingested)
    logger.info("Dupes skipped   : %d", dupes)
    logger.info("No CC skipped   : %d", no_cc)
    logger.info("Invalid skipped : %d", skipped)
    logger.info("Errors          : %d", errors)
    logger.info("By content_type : %s", content_type_counts)


if __name__ == "__main__":
    run()
