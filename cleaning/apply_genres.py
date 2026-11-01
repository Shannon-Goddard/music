"""
Apply strict genre mapping to catalog.

Logic per row:
  1. Try resolve_genre(genre)          — direct map on genre field
  2. If no hit, try resolve_tags(tags) — scan tags tokens
  3. If still no hit, genre_resolved = "" (blank = unresolved, original genre preserved)

Output:
  cleaning/catalog_genre_applied.csv   — full catalog + genre_resolved column
  cleaning/genre_unresolved.txt        — distinct unresolved genre values with counts

Run: python cleaning/apply_genres.py
"""
import csv
from collections import Counter
from map_genres import resolve_genre, resolve_tags

IN  = "cleaning/catalog_clean_genre.csv"
OUT = "cleaning/catalog_genre_applied.csv"
UNRESOLVED_REPORT = "cleaning/genre_unresolved.txt"

total = mapped_genre = mapped_tags = unresolved = 0
unresolved_counter = Counter()

with open(IN, encoding="utf-8") as fin, \
     open(OUT, "w", encoding="utf-8", newline="") as fout:

    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=reader.fieldnames + ["genre_resolved"])
    writer.writeheader()

    for row in reader:
        total += 1
        raw_genre = row["genre"].strip()
        tags      = row["tags"].strip()

        resolved = resolve_genre(raw_genre)
        if resolved:
            mapped_genre += 1
        else:
            resolved = resolve_tags(tags)
            if resolved:
                mapped_tags += 1
            else:
                unresolved += 1
                unresolved_counter[raw_genre] += 1

        row["genre_resolved"] = resolved or ""
        writer.writerow(row)

# ── Unresolved report ──
lines = [
    f"TOTAL          : {total:,}",
    f"mapped (genre) : {mapped_genre:,}  ({mapped_genre/total*100:.1f}%)",
    f"mapped (tags)  : {mapped_tags:,}  ({mapped_tags/total*100:.1f}%)",
    f"unresolved     : {unresolved:,}  ({unresolved/total*100:.1f}%)",
    "",
    f"{'Raw genre value':<50} {'Count':>7}",
    "-" * 60,
]
for val, cnt in unresolved_counter.most_common():
    lines.append(f"{val:<50} {cnt:>7}")

report = "\n".join(lines)
with open(UNRESOLVED_REPORT, "w", encoding="utf-8") as f:
    f.write(report)

print(report[:800].encode("ascii", "replace").decode())
print(f"\nFull unresolved list -> {UNRESOLVED_REPORT}")
print(f"Output CSV           -> {OUT}")
