"""
Pass 4 — duration outlier probe.
Checks for zero, suspiciously short, and absurdly long durations.
"""
import csv

IN = "cleaning/catalog_clean_unknown.csv"

with open(IN, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

present = [r for r in rows if r["duration_sec"].strip()]

zero       = [r for r in present if float(r["duration_sec"]) == 0]
under_5    = [r for r in present if 0 < float(r["duration_sec"]) < 5]
over_1hr   = [r for r in present if float(r["duration_sec"]) > 3600]
over_3hr   = [r for r in present if float(r["duration_sec"]) > 10800]

print(f"Has duration_sec : {len(present):,}")
print(f"Zero (0s)        : {len(zero):,}")
print(f"Under 5s         : {len(under_5):,}")
print(f"Over 1hr         : {len(over_1hr):,}")
print(f"Over 3hr         : {len(over_3hr):,}")

print(f"\nTop 10 longest:")
for r in sorted(present, key=lambda x: float(x["duration_sec"]), reverse=True)[:10]:
    d = float(r["duration_sec"])
    print(f"  {d:>12,.0f}s  ({d/3600:.1f}hr)  [{r['source_platform']}]  {r['artist_name']} -- {r['title']}")

print(f"\nSample zero-duration tracks:")
for r in zero[:5]:
    print(f"  [{r['source_platform']}]  {r['artist_name']} -- {r['title']}")
