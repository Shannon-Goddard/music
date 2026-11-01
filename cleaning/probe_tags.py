"""
Probe the tags field to understand structure and coverage.

Outputs:
  - tags_audit.txt  — distinct tag tokens with counts (sorted by frequency)

Run: python cleaning/probe_tags.py
"""
import csv
from collections import Counter

genre_has_value = 0
genre_empty_tags_have_value = 0
genre_empty_tags_empty = 0

tag_token_counter = Counter()   # individual tokens across all rows
tag_string_samples = []         # raw tag strings from null-genre rows

with open("cleaning/catalog_clean_stream_url.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        genre = row["genre"].strip()
        tags  = row["tags"].strip()

        if genre:
            genre_has_value += 1
        elif tags:
            genre_empty_tags_have_value += 1
            if len(tag_string_samples) < 20:
                tag_string_samples.append(tags)
        else:
            genre_empty_tags_empty += 1

        # Tokenize tags regardless of genre — understand the full tag vocabulary
        if tags:
            for tok in tags.replace(";", ",").replace("|", ",").split(","):
                tok = tok.strip().lower()
                if tok:
                    tag_token_counter[tok] += 1

lines = [
    "=== Coverage ===",
    f"genre has value                  : {genre_has_value:,}",
    f"genre empty, tags has value      : {genre_empty_tags_have_value:,}",
    f"genre empty, tags also empty     : {genre_empty_tags_empty:,}",
    "",
    "=== Sample raw tag strings (null-genre rows) ===",
]
for s in tag_string_samples:
    lines.append(f"  {s}")

lines += [
    "",
    f"=== Top 200 tag tokens (all rows) ===",
    f"{'Token':<40} {'Count':>7}",
    "-" * 50,
]
for tok, cnt in tag_token_counter.most_common(200):
    lines.append(f"{tok:<40} {cnt:>7}")

out = "\n".join(lines)
with open("cleaning/tags_audit.txt", "w", encoding="utf-8") as f:
    f.write(out)

print("\n".join(lines[:30]))
print(f"\n... full output -> cleaning/tags_audit.txt")
