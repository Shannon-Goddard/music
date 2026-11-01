import csv
from collections import Counter

platform     = Counter()
genre        = Counter()
content_type = Counter()
health       = Counter()
no_title = no_artist = no_genre = no_duration = no_cover = no_lang = 0
total = 0

with open("cleaning/catalog_review.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        total += 1
        platform[row["source_platform"] or "MISSING"] += 1
        genre[row["genre"] or "MISSING"] += 1
        content_type[row["content_type"] or "MISSING"] += 1
        health[row["health_status"] or "MISSING"] += 1
        if not row["title"].strip():       no_title    += 1
        if not row["artist_name"].strip(): no_artist   += 1
        if not row["genre"].strip():       no_genre    += 1
        if not row["duration_sec"].strip():no_duration += 1
        if not row["cover_art_url"].strip():no_cover   += 1
        if not row["language"].strip():    no_lang     += 1

lines = []
lines.append(f"TOTAL RECORDS: {total:,}\n")

lines.append("\n--- BY PLATFORM ---")
for k, v in platform.most_common():
    lines.append(f"  {k:<25} {v:>7,}  ({v/total*100:.1f}%)")

lines.append("\n--- BY CONTENT TYPE ---")
for k, v in content_type.most_common():
    lines.append(f"  {k:<25} {v:>7,}  ({v/total*100:.1f}%)")

lines.append("\n--- BY HEALTH STATUS ---")
for k, v in health.most_common():
    lines.append(f"  {k:<25} {v:>7,}  ({v/total*100:.1f}%)")

lines.append("\n--- TOP 25 GENRES ---")
for k, v in genre.most_common(25):
    lines.append(f"  {k:<25} {v:>7,}  ({v/total*100:.1f}%)")

lines.append("\n--- MISSING FIELDS (enrichment opportunities) ---")
lines.append(f"  no title        {no_title:>7,}  ({no_title/total*100:.1f}%)")
lines.append(f"  no artist       {no_artist:>7,}  ({no_artist/total*100:.1f}%)")
lines.append(f"  no genre        {no_genre:>7,}  ({no_genre/total*100:.1f}%)")
lines.append(f"  no duration     {no_duration:>7,}  ({no_duration/total*100:.1f}%)")
lines.append(f"  no cover art    {no_cover:>7,}  ({no_cover/total*100:.1f}%)")
lines.append(f"  no language     {no_lang:>7,}  ({no_lang/total*100:.1f}%)")

out = "\n".join(lines)
with open("cleaning/catalog_summary.txt", "w", encoding="utf-8") as f:
    f.write(out)

print("Done. See cleaning/catalog_summary.txt")
