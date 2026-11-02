"""
Remove any genre attribute that isn't one of the 15 canonical genres.
Scans the full table, checks genre value, REMOVEs if not canonical.

Dry-run by default. Pass --live to apply.
"""
import sys
import time
import boto3
from botocore.exceptions import ClientError

DRY_RUN = "--live" not in sys.argv
TABLE   = "music-tracks"

CANONICAL = {
    "electronic", "ambient", "jazz", "classical", "blues", "rock",
    "hip-hop", "folk", "country", "metal", "punk", "reggae", "soul",
    "experimental", "pop", "industrial"
}

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table    = dynamodb.Table(TABLE)

to_remove = []

kwargs = {"ProjectionExpression": "track_id, genre"}
while True:
    resp = table.scan(**kwargs)
    for item in resp["Items"]:
        g = item.get("genre")
        if g and g not in CANONICAL:
            to_remove.append(item["track_id"])
    if "LastEvaluatedKey" not in resp:
        break
    kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

print(f"Non-canonical genre rows: {len(to_remove):,}")

if DRY_RUN:
    print("[DRY RUN] — pass --live to apply.")
    sys.exit(0)

errors = 0
for i, tid in enumerate(to_remove):
    for attempt in range(5):
        try:
            table.update_item(
                Key={"track_id": tid},
                UpdateExpression="REMOVE genre",
            )
            break
        except ClientError as e:
            if e.response["Error"]["Code"] == "ProvisionedThroughputExceededException":
                time.sleep(2 ** attempt * 0.5)
            else:
                print(f"ERROR {tid}: {e}")
                errors += 1
                break
    if (i + 1) % 500 == 0:
        print(f"  {i+1:,} / {len(to_remove):,}")

print(f"\nDone. Removed: {len(to_remove) - errors:,}  Errors: {errors:,}")
