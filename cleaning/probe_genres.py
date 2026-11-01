"""
Full genre audit — all values, counts, and which platforms they come from.
"""
import csv
from collections import Counter, defaultdict

genre_count = Counter()
genre_platform = defaultdict(Counter)

with open("cleaning/catalog_clean_stream_url.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        g = row["genre"] or "MISSING"
        genre_count[g] += 1
        genre_platform[g][row["source_platform"]] += 1

with open("cleaning/genre_audit.txt", "w", encoding="utf-8") as out:
    out.write(f"Total distinct genre values: {len(genre_count)}\n\n")
    out.write(f"{'Genre':<35} {'Count':>7}  Platforms\n")
    out.write("-" * 80 + "\n")
    for g, count in genre_count.most_common():
        platforms = "  ".join(f"{p}:{n}" for p, n in genre_platform[g].most_common())
        out.write(f"{g:<35} {count:>7}  {platforms}\n")

print("Done -> cleaning/genre_audit.txt")
