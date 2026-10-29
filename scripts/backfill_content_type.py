"""
Backfill content_type on existing DynamoDB records that are missing it.
Scans for items without content_type, classifies from tags + title,
then writes only those items.

Usage:
    python scripts/backfill_content_type.py
"""

import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = "music-tracks"
REGION     = "us-east-1"

_LECTURE_WORDS   = {"lecture", "sermon", "speech", "talk", "lesson", "class", "course", "seminar"}
_INTERVIEW_WORDS = {"interview", "conversation", "discussion", "q&a"}
_PODCAST_WORDS   = {"podcast", "episode", "show", "broadcast"}
_AUDIOBOOK_WORDS = {"audiobook", "reading", "narration", "story", "chapter"}
_MUSIC_WORDS     = {"music", "song", "album", "instrumental", "jazz", "rock", "classical",
                    "folk", "electronic", "blues", "ambient", "pop", "hip-hop", "soundtrack",
                    "band", "orchestra", "concert", "live", "single", "ep", "lp"}


def _detect(tags: list, title: str) -> str:
    tokens = {w.lower() for s in tags for w in str(s).replace("-", " ").split()}
    tokens |= {w.lower() for w in title.replace("-", " ").split()}
    if tokens & _LECTURE_WORDS:   return "lecture"
    if tokens & _INTERVIEW_WORDS: return "interview"
    if tokens & _PODCAST_WORDS:   return "podcast"
    if tokens & _AUDIOBOOK_WORDS: return "audiobook"
    if tokens & _MUSIC_WORDS:     return "music"
    return "other"


def run():
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
    updated, errors, counts = 0, 0, {}

    scan_kwargs = {"FilterExpression": Attr("content_type").not_exists()}
    while True:
        resp = table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            ct = _detect(item.get("tags") or [], item.get("title", ""))
            counts[ct] = counts.get(ct, 0) + 1
            try:
                table.update_item(
                    Key={"track_id": item["track_id"]},
                    UpdateExpression="SET content_type = :ct",
                    ExpressionAttributeValues={":ct": ct},
                )
                updated += 1
            except Exception as e:
                print(f"  ERROR {item.get('track_id')}: {e}")
                errors += 1

        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        scan_kwargs["ExclusiveStartKey"] = last

    print(f"\nDone — updated {updated}, errors {errors}")
    print("Breakdown:", counts)


if __name__ == "__main__":
    run()
