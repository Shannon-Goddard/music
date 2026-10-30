"""
Test whether Jamendo's built-in CC license filter params (ccsa, ccnd, ccnc)
unlock more CC tracks than our tag-sweep approach.
Run: python scripts/probe_jamendo_cc_filter.py
"""
import requests, time

CLIENT_ID = "f15a1ec3"
BASE = "https://api.jamendo.com/v3.0/tracks/"


def depth(params, label, page_cap=100):
    total = 0
    for page in range(page_cap):
        r = requests.get(BASE, params={
            **params,
            "client_id": CLIENT_ID,
            "format": "json",
            "limit": 200,
            "audioformat": "mp32",
            "offset": page * 200,
        }, timeout=15)
        d = r.json()
        n = d["headers"]["results_count"]
        total += n
        if page == 0 or page % 10 == 0:
            results = d.get("results", [])
            cc = sum(1 for t in results if "creativecommons" in (t.get("license_ccurl") or ""))
            print(f"  [{label}] page {page:3d}  offset {page*200:6d}  results={n}  cc={cc}/{len(results)}")
        if n < 200:
            break
        time.sleep(0.05)
    return total


print("=== CC filter: ccsa=1 (share-alike only) ===")
n = depth({"ccsa": 1, "order": "releasedate_desc"}, "ccsa")
print(f"  Total: {n:,}\n")

print("=== CC filter: ccnd=1 (no-derivatives only) ===")
n = depth({"ccnd": 1, "order": "releasedate_desc"}, "ccnd")
print(f"  Total: {n:,}\n")

print("=== CC filter: ccnc=1 (non-commercial only) ===")
n = depth({"ccnc": 1, "order": "releasedate_desc"}, "ccnc")
print(f"  Total: {n:,}\n")

print("=== CC filter: all three combined (ccsa=1&ccnd=1&ccnc=1) ===")
n = depth({"ccsa": 1, "ccnd": 1, "ccnc": 1, "order": "releasedate_desc"}, "all-cc")
print(f"  Total: {n:,}\n")

print("=== CC filter: ccsa=1 ordered by id_asc (different ordering) ===")
n = depth({"ccsa": 1, "order": "id_asc"}, "ccsa-id_asc")
print(f"  Total: {n:,}\n")
