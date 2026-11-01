"""
Delete rows with junk genre values.

Criteria — delete if genre matches any of:
  - Mystery* variants (any genre starting with "Mystery" or "Misterio")
  - Known internal codes / keyboard mash / format labels / pure noise

Input:  cleaning/catalog_clean_stream_url.csv
Output: cleaning/catalog_clean_genre.csv
Report: prints deleted count by genre value

Run: python cleaning/delete_rows.py
"""
import csv
import re

IN  = "cleaning/catalog_clean_stream_url.csv"
OUT = "cleaning/catalog_clean_genre.csv"

# Exact-match junk genres (lowercased for comparison)
JUNK_EXACT = {
    # Internal codes
    "nsfri", "nssun",
    # Keyboard mash
    "asdsad", "asdsadasd", "adsasda", "djjdj", "jsjdjs", "ldldldl",
    "ndndkwosk", "jdjd jej",
    # Format labels
    "pdf", "dvd-video", "mp3", "mp4", "vinyl", "cd", "lp", "ep", "tape",
    # Pure noise
    "shitpost", "shit", "cunt", "pussy",
    # Single chars / punctuation
    ".", "-", "a", "s", "t", "e", "q", "na", "ok",
}

# Prefix patterns (case-insensitive)
JUNK_PREFIXES = (
    "mystery",   # Mystery, Mystery Metal, Mystery Blues, Mystery Zone, etc.
    "misterio",  # Spanish variant
)

def is_junk(genre: str) -> bool:
    low = genre.strip().lower()
    if low in JUNK_EXACT:
        return True
    if any(low.startswith(p) for p in JUNK_PREFIXES):
        return True
    return False


kept = deleted = 0
deleted_counts = {}

with open(IN, encoding="utf-8") as fin, \
     open(OUT, "w", encoding="utf-8", newline="") as fout:

    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
    writer.writeheader()

    for row in reader:
        genre = row["genre"].strip()
        if is_junk(genre):
            deleted += 1
            deleted_counts[genre] = deleted_counts.get(genre, 0) + 1
        else:
            kept += 1
            writer.writerow(row)

print(f"Deleted : {deleted:,}")
print(f"Kept    : {kept:,}")
print(f"\nDeleted by genre value:")
for g, c in sorted(deleted_counts.items(), key=lambda x: -x[1]):
    print(f"  {g:<50} {c:>5}")
print(f"\nOutput -> {OUT}")
