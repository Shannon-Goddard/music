"""
Pass 3 — Duplicate detail report.
For each exact dupe group (title+artist+platform), lists all stream_urls
so you can tell true dupes (same recording, different IA collection)
from same-title different-recordings.

Output: cleaning/dupes_review.csv
"""
import csv
from collections import defaultdict

IN  = "cleaning/catalog_genre_applied.csv"
OUT = "cleaning/dupes_review.csv"

with open(IN, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

# Group by title+artist+platform
groups = defaultdict(list)
for r in rows:
    key = (r["title"].strip().lower(), r["artist_name"].strip().lower(), r["source_platform"].strip())
    groups[key].append(r)

dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}

with open(OUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["group_id", "count", "title", "artist_name", "platform", "track_id", "ia_collection", "stream_url", "duration_sec"])

    for i, ((title, artist, platform), tracks) in enumerate(
        sorted(dupe_groups.items(), key=lambda x: -len(x[1])), start=1
    ):
        for t in tracks:
            writer.writerow([
                i,
                len(tracks),
                t["title"],
                t["artist_name"],
                platform,
                t["track_id"],
                t.get("ia_collection", ""),
                t["stream_url"],
                t.get("duration_sec", ""),
            ])

print(f"Wrote {len(dupe_groups):,} dupe groups to {OUT}")
