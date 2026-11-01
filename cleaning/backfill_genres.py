"""
Genre backfill — writes genre_resolved to DynamoDB.

  - genre_resolved has a value  → SET genre = <canonical>
  - genre_resolved is blank     → REMOVE genre attribute

Uses batch_writer for SET rows (25 per request).
REMOVE rows are done individually (batch_writer only supports PutItem/DeleteItem).
Both paths retry on ProvisionedThroughputExceededException.

Dry-run by default. Pass --live to write.

Run:
  python cleaning/backfill_genres.py           # dry-run
  python cleaning/backfill_genres.py --live    # live writes
"""
import csv
import sys
import time
import boto3
from botocore.exceptions import ClientError

DRY_RUN    = "--live" not in sys.argv
TABLE_NAME = "music-tracks"
IN         = "cleaning/catalog_genre_applied.csv"

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table    = dynamodb.Table(TABLE_NAME)

# Split rows into two buckets
set_rows    = []   # (track_id, genre)
remove_rows = []   # track_id

with open(IN, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        track_id = row["track_id"].strip()
        resolved = row["genre_resolved"].strip()
        if resolved:
            set_rows.append((track_id, resolved))
        else:
            remove_rows.append(track_id)

print(f"SET rows    : {len(set_rows):,}")
print(f"REMOVE rows : {len(remove_rows):,}")

if DRY_RUN:
    print("\n[DRY RUN] — pass --live to apply.")
    sys.exit(0)

errors = 0

# ── SET rows via batch_writer (25 per request, auto-retries unprocessed) ──
# batch_writer only supports put_item, so we put the full minimal item.
# We only want to update genre — use update_item in chunks instead.
CHUNK = 25

def update_with_retry(tid, genre, retries=5):
    for attempt in range(retries):
        try:
            table.update_item(
                Key={"track_id": tid},
                UpdateExpression="SET genre = :g",
                ExpressionAttributeValues={":g": genre},
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
                time.sleep(2 ** attempt * 0.5)
            else:
                print(f"ERROR SET {tid}: {e}")
                return False
    print(f"ERROR SET {tid}: max retries exceeded")
    return False

def remove_with_retry(tid, retries=5):
    for attempt in range(retries):
        try:
            table.update_item(
                Key={"track_id": tid},
                UpdateExpression="REMOVE genre",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
                time.sleep(2 ** attempt * 0.5)
            else:
                print(f"ERROR REMOVE {tid}: {e}")
                return False
    print(f"ERROR REMOVE {tid}: max retries exceeded")
    return False

# Process SET rows
print(f"\nWriting {len(set_rows):,} SET updates...")
for i, (tid, genre) in enumerate(set_rows):
    if not update_with_retry(tid, genre):
        errors += 1
    if (i + 1) % 1000 == 0:
        print(f"  {i+1:,} / {len(set_rows):,}")

# Process REMOVE rows
print(f"\nWriting {len(remove_rows):,} REMOVE updates...")
for i, tid in enumerate(remove_rows):
    if not remove_with_retry(tid):
        errors += 1
    if (i + 1) % 1000 == 0:
        print(f"  {i+1:,} / {len(remove_rows):,}")

print(f"\n[LIVE]")
print(f"  Updated (SET genre)   : {len(set_rows) - errors:,}")
print(f"  Nulled (REMOVE genre) : {len(remove_rows):,}")
print(f"  Errors                : {errors:,}")
