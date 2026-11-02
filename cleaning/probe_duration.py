"""
Pass 4 — duration_sec probe.
Reports missing duration_sec by platform and content_type.
"""
import csv
from collections import Counter

IN = "cleaning/catalog_clean_unknown.csv"

with open(IN, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

missing = [r for r in rows if not r["duration_sec"].strip()]
present = [r for r in rows if r["duration_sec"].strip()]

print(f"Total rows       : {len(rows):,}")
print(f"Has duration_sec : {len(present):,}")
print(f"Missing          : {len(missing):,}  ({len(missing)/len(rows)*100:.1f}%)")

print(f"\nMissing by platform:")
for p, count in Counter(r["source_platform"] for r in missing).most_common():
    print(f"  {p:<20} {count:,}")

print(f"\nMissing by content_type:")
for ct, count in Counter(r["content_type"] for r in missing).most_common():
    print(f"  {ct:<20} {count:,}")

# Duration stats for present rows
durations = [float(r["duration_sec"]) for r in present]
durations.sort()
print(f"\nDuration stats (present rows):")
print(f"  Min    : {durations[0]:.0f}s")
print(f"  Median : {durations[len(durations)//2]:.0f}s")
print(f"  Max    : {durations[-1]:.0f}s")
print(f"  >1hr   : {sum(1 for d in durations if d > 3600):,}")
