"""
Pass 3 — True duplicate check by stream_url.
A duplicate stream_url = same file ingested twice from different IA collections.
"""
import csv
from collections import defaultdict

IN  = "cleaning/catalog_genre_applied.csv"
OUT = "cleaning/true_dupes.csv"

with open(IN, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

groups = defaultdict(list)
for r in rows:
    groups[r["stream_url"].strip()].append(r)

dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}

extra_rows = sum(len(v) - 1 for v in dupe_groups.values())
print(f"Duplicate stream_urls : {len(dupe_groups):,} groups")
print(f"Extra rows to delete  : {extra_rows:,}")

with open(OUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["group_id", "count", "track_id", "title", "artist_name", "ia_collection", "stream_url"])
    for i, (url, tracks) in enumerate(sorted(dupe_groups.items(), key=lambda x: -len(x[1])), start=1):
        for t in tracks:
            writer.writerow([i, len(tracks), t["track_id"], t["title"], t["artist_name"], t.get("ia_collection", ""), url])

print(f"Written to {OUT}")
