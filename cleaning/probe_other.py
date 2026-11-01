"""
Audit content_type=other rows to understand what they actually are.
"""
import csv
from collections import Counter

lang = Counter()
platform = Counter()
collection = Counter()
genre = Counter()
total_other = 0

with open("cleaning/catalog_clean_stream_url.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["content_type"] != "other":
            continue
        total_other += 1
        lang[row["language"] or "none"] += 1
        platform[row["source_platform"] or "none"] += 1
        collection[row["ia_collection"] or "none"] += 1
        genre[row["genre"] or "none"] += 1

with open("cleaning/other_audit.txt", "w", encoding="utf-8") as out:
    out.write(f"content_type=other total: {total_other:,}\n")

    out.write("\n--- BY LANGUAGE ---\n")
    for k, v in lang.most_common():
        out.write(f"  {k:<12} {v:>7,}  ({v/total_other*100:.1f}%)\n")

    out.write("\n--- BY PLATFORM ---\n")
    for k, v in platform.most_common():
        out.write(f"  {k:<25} {v:>7,}  ({v/total_other*100:.1f}%)\n")

    out.write("\n--- BY IA COLLECTION ---\n")
    for k, v in collection.most_common():
        out.write(f"  {k:<30} {v:>7,}  ({v/total_other*100:.1f}%)\n")

    out.write("\n--- BY GENRE ---\n")
    for k, v in genre.most_common(30):
        out.write(f"  {k:<25} {v:>7,}  ({v/total_other*100:.1f}%)\n")

print("Done -> cleaning/other_audit.txt")
