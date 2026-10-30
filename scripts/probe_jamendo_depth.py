"""
Probe Jamendo API depth:
1. How deep can we paginate a single tag before hitting empty?
2. Does the API have a hard offset cap?
3. What does the /artists and /albums endpoint expose?
Run: python scripts/probe_jamendo_depth.py
"""
import requests

CLIENT_ID = "f15a1ec3"
BASE = "https://api.jamendo.com/v3.0/"


def fetch(endpoint, params, timeout=15):
    r = requests.get(BASE + endpoint, params=params, timeout=timeout)
    return r.json()


# 1. How deep does 'jazz' go?
print("=== Depth probe: jazz ===")
for offset in [0, 200, 400, 600, 800, 1000, 1400, 1800, 2000, 3000, 4000, 5000]:
    d = fetch("tracks/", {
        "client_id": CLIENT_ID, "format": "json", "limit": 200,
        "audioformat": "mp32", "tags": "jazz", "offset": offset
    })
    count = d["headers"]["results_count"]
    print(f"  offset {offset:5d}: {count} results")
    if count == 0:
        print("  => hit wall")
        break

# 2. Does unfiltered go deeper than 400?
print("\n=== Depth probe: unfiltered ===")
for offset in [0, 200, 400, 600, 800, 1000]:
    d = fetch("tracks/", {
        "client_id": CLIENT_ID, "format": "json", "limit": 200,
        "audioformat": "mp32", "order": "releasedate_desc", "offset": offset
    })
    count = d["headers"]["results_count"]
    print(f"  offset {offset:5d}: {count} results")
    if count == 0:
        print("  => hit wall")
        break

# 3. Try /artists endpoint — how many artists?
print("\n=== Artists endpoint depth ===")
for offset in [0, 200, 400, 600]:
    d = fetch("artists/", {
        "client_id": CLIENT_ID, "format": "json", "limit": 200, "offset": offset
    })
    count = d["headers"]["results_count"]
    print(f"  offset {offset:5d}: {count} artists")
    if count == 0:
        break

# 4. Try /albums endpoint
print("\n=== Albums endpoint depth ===")
for offset in [0, 200, 400, 600]:
    d = fetch("albums/", {
        "client_id": CLIENT_ID, "format": "json", "limit": 200, "offset": offset
    })
    count = d["headers"]["results_count"]
    print(f"  offset {offset:5d}: {count} albums")
    if count == 0:
        break

# 5. Try tracks ordered by id (ascending) — different ordering might unlock more
print("\n=== Depth probe: order by id asc ===")
for offset in [0, 200, 400, 600, 1000, 2000, 5000, 10000, 50000, 100000, 200000]:
    d = fetch("tracks/", {
        "client_id": CLIENT_ID, "format": "json", "limit": 1,
        "audioformat": "mp32", "order": "id_asc", "offset": offset
    })
    count = d["headers"]["results_count"]
    results = d.get("results", [])
    track_id = results[0].get("id") if results else "none"
    print(f"  offset {offset:7d}: {count} results  track_id={track_id}")
    if count == 0:
        print("  => hit wall")
        break
