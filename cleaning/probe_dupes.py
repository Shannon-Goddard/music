"""
Pass 3 — Duplicate probe.
Checks for exact dupes (same title+artist+platform) and cross-platform dupes.
"""
import csv
from collections import Counter

IN = "cleaning/catalog_genre_applied.csv"

with open(IN, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows):,}")

exact = Counter(
    (r["title"].strip().lower(), r["artist_name"].strip().lower(), r["source_platform"].strip())
    for r in rows
)
exact_dupes = {k: v for k, v in exact.items() if v > 1}

cross = Counter(
    (r["title"].strip().lower(), r["artist_name"].strip().lower())
    for r in rows
)
cross_dupes = {k: v for k, v in cross.items() if v > 1}

print(f"Exact dupes (title+artist+platform) : {sum(v-1 for v in exact_dupes.values()):,} extra rows in {len(exact_dupes):,} groups")
print(f"Cross-platform dupes (title+artist) : {sum(v-1 for v in cross_dupes.values()):,} extra rows in {len(cross_dupes):,} groups")

print("\nTop 20 exact dupe groups:")
for (title, artist, platform), count in sorted(exact_dupes.items(), key=lambda x: -x[1])[:20]:
    print(f"  {count}x  [{platform}]  {artist} -- {title}")

print("\nTop 20 cross-platform dupe groups:")
for (title, artist), count in sorted(cross_dupes.items(), key=lambda x: -x[1])[:20]:
    print(f"  {count}x  {artist} -- {title}")
