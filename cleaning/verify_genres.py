"""
Verify genre backfill results against DynamoDB.
Scans the full table and reports:
  - Total rows
  - Rows with genre set vs null
  - Genre distribution
"""
import boto3
from collections import Counter

TABLE = "music-tracks"
dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table(TABLE)

total = 0
with_genre = 0
without_genre = 0
genre_counts = Counter()

kwargs = {"ProjectionExpression": "genre"}
while True:
    resp = table.scan(**kwargs)
    for item in resp["Items"]:
        total += 1
        g = item.get("genre")
        if g:
            with_genre += 1
            genre_counts[g] += 1
        else:
            without_genre += 1
    if "LastEvaluatedKey" not in resp:
        break
    kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

print(f"Total rows      : {total:,}")
print(f"With genre      : {with_genre:,}")
print(f"Without genre   : {without_genre:,}")
print(f"\nGenre distribution:")
for genre, count in sorted(genre_counts.items(), key=lambda x: -x[1]):
    print(f"  {genre:<20} {count:,}")
