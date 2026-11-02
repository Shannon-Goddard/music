"""
Pass 3 step 2 — Delete unidentifiable tracks.
Rows where both title AND artist are unknown/blank.
Deletes from DynamoDB and writes cleaned CSV.

Dry-run by default. Pass --live to apply.
"""
import csv
import sys
import time
import boto3
from botocore.exceptions import ClientError

DRY_RUN = "--live" not in sys.argv
TABLE   = "cleaning/catalog_genre_applied.csv"
OUT     = "cleaning/catalog_clean_unknown.csv"

UNKNOWN = {"unknown artist", "unknown", "", "-", "none legible", "none listed"}

with open(TABLE, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
    fieldnames = csv.DictReader(open(TABLE, encoding="utf-8")).fieldnames

to_delete = [
    r for r in rows
    if r["artist_name"].strip().lower() in UNKNOWN
    and r["title"].strip().lower() in UNKNOWN
]
to_keep = [r for r in rows if r not in to_delete]

print(f"Total rows    : {len(rows):,}")
print(f"To delete     : {len(to_delete):,}")
print(f"To keep       : {len(to_keep):,}")

if DRY_RUN:
    print("\n[DRY RUN] — pass --live to apply.")
    sys.exit(0)

# Delete from DynamoDB
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table    = dynamodb.Table("music-tracks")

errors = 0
for i, r in enumerate(to_delete):
    for attempt in range(5):
        try:
            table.delete_item(Key={"track_id": r["track_id"]})
            break
        except ClientError as e:
            if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
                time.sleep(2 ** attempt * 0.5)
            else:
                print(f"ERROR {r['track_id']}: {e}")
                errors += 1
                break

# Write cleaned CSV
with open(OUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(to_keep)

print(f"\n[LIVE]")
print(f"  Deleted from DynamoDB : {len(to_delete) - errors:,}")
print(f"  Errors                : {errors:,}")
print(f"  Written to            : {OUT} ({len(to_keep):,} rows)")
