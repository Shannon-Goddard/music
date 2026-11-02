"""
Probe unidentifiable tracks — title or artist is unknown/blank.
"""
import csv
from collections import Counter

IN = "cleaning/catalog_genre_applied.csv"

UNKNOWN = {"unknown artist", "unknown", "", "-", "none legible", "none listed"}

with open(IN, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

unknown_artist = [r for r in rows if r["artist_name"].strip().lower() in UNKNOWN]
unknown_title  = [r for r in rows if r["title"].strip().lower() in UNKNOWN]
both_unknown   = [r for r in rows if r["artist_name"].strip().lower() in UNKNOWN and r["title"].strip().lower() in UNKNOWN]

print(f"Total rows          : {len(rows):,}")
print(f"Unknown artist      : {len(unknown_artist):,}")
print(f"Unknown title       : {len(unknown_title):,}")
print(f"Both unknown        : {len(both_unknown):,}")

print(f"\nContent type breakdown (both unknown):")
for ct, count in Counter(r["content_type"] for r in both_unknown).most_common():
    print(f"  {ct:<20} {count:,}")

print(f"\nPlatform breakdown (both unknown):")
for p, count in Counter(r["source_platform"] for r in both_unknown).most_common():
    print(f"  {p:<20} {count:,}")

print(f"\nGenre breakdown (both unknown):")
for g, count in Counter(r["genre_resolved"] or "null" for r in both_unknown).most_common(10):
    print(f"  {g:<20} {count:,}")
