"""
Export full DynamoDB catalog to CSV for review.
Columns chosen to surface cleaning + enrichment opportunities.
Run: python scripts/export_catalog_csv.py
Output: scripts/catalog_review.csv
"""
import csv
import sys
import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = "music-tracks"
REGION     = "us-east-1"
OUT_FILE   = "cleaning/catalog_review.csv"

FIELDS = [
    "track_id", "title", "artist_name", "album_title",
    "genre", "content_type", "source_platform", "ia_collection",
    "language", "duration_sec", "cover_art_url", "stream_url",
    "license_type", "is_downloadable", "health_status",
    "mood", "tags", "attribution_text", "added_at",
]

def scan_all(table):
    kwargs = {}
    while True:
        resp = table.scan(**kwargs)
        yield from resp.get("Items", [])
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last

def main():
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
    print("Scanning DynamoDB — this may take a minute...")

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        count = 0
        for item in scan_all(table):
            # Flatten tags list to pipe-separated string
            if isinstance(item.get("tags"), list):
                item["tags"] = "|".join(item["tags"])
            writer.writerow({k: item.get(k, "") for k in FIELDS})
            count += 1
            if count % 5000 == 0:
                print(f"  {count:,} records written...")

    print(f"\nDone: {count:,} records -> {OUT_FILE}")

if __name__ == "__main__":
    main()
