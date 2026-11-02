"""
Pass 4 — Null out zero duration_sec values.
Rows where duration_sec = 0 get REMOVE duration_sec in DynamoDB.

Dry-run by default. Pass --live to apply.
"""
import csv
import sys
import time
import boto3
from botocore.exceptions import ClientError

DRY_RUN = "--live" not in sys.argv
IN      = "cleaning/catalog_clean_unknown.csv"
OUT     = "cleaning/catalog_final.csv"

with open(IN, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

to_fix = [r for r in rows if r["duration_sec"].strip() == "0"]
print(f"Total rows       : {len(rows):,}")
print(f"Zero duration    : {len(to_fix):,}")

if DRY_RUN:
    print("\n[DRY RUN] — pass --live to apply.")
    sys.exit(0)

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table    = dynamodb.Table("music-tracks")

errors = 0
for r in to_fix:
    for attempt in range(5):
        try:
            table.update_item(
                Key={"track_id": r["track_id"]},
                UpdateExpression="REMOVE duration_sec",
            )
            break
        except ClientError as e:
            if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
                time.sleep(2 ** attempt * 0.5)
            else:
                print(f"ERROR {r['track_id']}: {e}")
                errors += 1
                break

# Write final CSV with zeros nulled
for r in to_fix:
    r["duration_sec"] = ""

with open(OUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n[LIVE]")
print(f"  Nulled in DynamoDB : {len(to_fix) - errors:,}")
print(f"  Errors             : {errors:,}")
print(f"  Written to         : {OUT} ({len(rows):,} rows)")
