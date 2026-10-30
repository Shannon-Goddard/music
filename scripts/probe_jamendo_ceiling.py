"""
Find Jamendo catalog ceiling and test bulk id_asc pagination.
Run: python scripts/probe_jamendo_ceiling.py
"""
import requests

CLIENT_ID = "f15a1ec3"
BASE = "https://api.jamendo.com/v3.0/tracks/"


def probe(offset, limit=1):
    r = requests.get(BASE, params={
        "client_id": CLIENT_ID, "format": "json", "limit": limit,
        "include": "musicinfo", "audioformat": "mp32",
        "order": "id_asc", "offset": offset
    }, timeout=15)
    d = r.json()
    results = d.get("results", [])
    count = d["headers"]["results_count"]
    return count, results


# Find ceiling
print("=== Finding catalog ceiling ===")
for offset in [250000, 270000, 280000, 283000, 285000, 290000, 300000, 350000]:
    count, results = probe(offset)
    tid = results[0].get("id") if results else "none"
    lic = results[0].get("license_ccurl", "no-license") if results else ""
    print(f"  offset {offset:7d}: {count} results  id={tid}  license={lic[:50] if lic else 'none'}")

# Test bulk fetch at a deep offset — does limit=200 work at offset 200000?
print("\n=== Bulk fetch test at offset 200000 (limit=200) ===")
count, results = probe(200000, limit=200)
cc = sum(1 for r in results if "creativecommons" in (r.get("license_ccurl") or ""))
print(f"  fetched: {count}  CC-licensed: {cc}/{len(results)}")
if results:
    print(f"  first: id={results[0]['id']} name={results[0]['name'][:40]}")
    print(f"  last:  id={results[-1]['id']} name={results[-1]['name'][:40]}")

# What fraction of tracks are CC-licensed across the catalog?
print("\n=== CC license sampling across catalog ===")
for offset in [0, 50000, 100000, 150000, 200000, 250000]:
    count, results = probe(offset, limit=200)
    if not results:
        print(f"  offset {offset:7d}: empty")
        continue
    cc = sum(1 for r in results if "creativecommons" in (r.get("license_ccurl") or ""))
    print(f"  offset {offset:7d}: {cc}/{len(results)} CC-licensed ({cc/len(results)*100:.0f}%)")
