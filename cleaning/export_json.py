"""
Export catalog_final.csv → data/ JSON chunks for static frontend.

Outputs:
  data/index.json              — manifest with counts and available chunks
  data/genre/<genre>.json      — all tracks per canonical genre
  data/type/<type>.json        — all tracks per content_type
  data/search-index.json       — lightweight {track_id, title, artist_name} for Fuse.js

Only fields needed by the frontend are included — strips tags, ia_collection,
mood, health_status, dataset_version, added_at, genre_resolved.
"""
import csv
import json
import os
from collections import defaultdict

IN  = "cleaning/catalog_final.csv"
OUT = "data"

KEEP = [
    "track_id", "title", "artist_name", "album_title", "album_id",
    "genre", "content_type", "source_platform", "language",
    "duration_sec", "cover_art_url", "stream_url", "license_type",
    "is_downloadable", "attribution_text", "source_url",
]

CANONICAL_GENRES = {
    "electronic", "ambient", "jazz", "classical", "blues", "rock",
    "hip-hop", "folk", "country", "metal", "punk", "reggae", "soul",
    "experimental", "pop", "industrial"
}

# Content types to export (skip music — too large, browsed by genre instead)
EXPORT_TYPES = {"audiobook", "podcast", "lecture", "interview"}


def coerce(row):
    t = {k: row.get(k, "").strip() or None for k in KEEP}
    if t["duration_sec"]:
        try:
            t["duration_sec"] = float(t["duration_sec"])
        except ValueError:
            t["duration_sec"] = None
    t["is_downloadable"] = row.get("is_downloadable", "").strip().upper() == "TRUE"
    # Only use genre_resolved if it's a canonical genre
    resolved = row.get("genre_resolved", "").strip()
    t["genre"] = resolved if resolved in CANONICAL_GENRES else None
    return t

# Read
with open(IN, encoding="utf-8") as f:
    rows = [coerce(r) for r in csv.DictReader(f)]

print(f"Loaded {len(rows):,} rows")

# Bucket by genre and content_type
by_genre = defaultdict(list)
by_type  = defaultdict(list)
search_index = []

for t in rows:
    if t["genre"]:
        by_genre[t["genre"]].append(t)
    if t["content_type"] and t["content_type"] in EXPORT_TYPES:
        by_type[t["content_type"]].append(t)
    search_index.append({
        "track_id":    t["track_id"],
        "title":       t["title"] or "",
        "artist_name": t["artist_name"] or "",
    })

# Create output dirs
os.makedirs(f"{OUT}/genre", exist_ok=True)
os.makedirs(f"{OUT}/type",  exist_ok=True)

# Write genre chunks
for genre, tracks in by_genre.items():
    path = f"{OUT}/genre/{genre}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  genre/{genre}.json — {len(tracks):,} tracks")

# Write type chunks
for ctype, tracks in by_type.items():
    path = f"{OUT}/type/{ctype}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  type/{ctype}.json — {len(tracks):,} tracks")

# Write search index
with open(f"{OUT}/search-index.json", "w", encoding="utf-8") as f:
    json.dump(search_index, f, ensure_ascii=False, separators=(",", ":"))
print(f"  search-index.json — {len(search_index):,} entries")

# Write index manifest
index = {
    "total_tracks": len(rows),
    "genres":       {g: len(t) for g, t in sorted(by_genre.items())},
    "types":        {c: len(t) for c, t in sorted(by_type.items())},
}
with open(f"{OUT}/index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)
print(f"  index.json written")
print(f"\nDone. {len(by_genre)} genre chunks, {len(by_type)} type chunks.")
