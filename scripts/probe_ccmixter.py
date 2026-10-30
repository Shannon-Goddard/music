"""
Probe ccMixter API — fixed version.
Run: python scripts/probe_ccmixter.py
"""
import requests, json

BASE = "https://ccmixter.org/api/query"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch(params):
    r = requests.get(BASE, params={"format": "json", **params}, headers=HEADERS, timeout=15)
    if not r.text.strip():
        return []
    try:
        return r.json()
    except Exception:
        return []


# 1. Full field map of one track
print("=== Full field map (1 track) ===")
results = fetch({"limit": 1})
if results:
    t = results[0]
    for k, v in t.items():
        val = json.dumps(v)[:120] if isinstance(v, (dict, list)) else str(v)[:120]
        print(f"  {k:<30} {val}")

# 2. Files array structure
print("\n=== Files array structure ===")
results = fetch({"limit": 3})
for t in results:
    print(f"  upload_id={t.get('upload_id')}  name={t.get('upload_name','?')[:40]}")
    for f in t.get("files", []):
        print(f"    file_id={f.get('file_id')}  name={f.get('file_name','?')[:50]}")
        print(f"    download_url={f.get('download_url','N/A')[:80]}")
        print(f"    file_format={f.get('file_format','?')}  file_type={f.get('file_type','?')}")

# 3. Pagination ceiling
print("\n=== Pagination ceiling ===")
for offset in [0, 1000, 3000, 5000, 7000, 9000, 10000, 12000, 15000]:
    results = fetch({"limit": 1, "offset": offset})
    name = results[0].get("upload_name", "EMPTY") if results else "EMPTY"
    print(f"  offset {offset:6d}: {'OK' if results else 'EMPTY':5s}  {name[:50]}")

# 4. Upload types across 200 tracks
print("\n=== Upload types (200 tracks) ===")
results = fetch({"limit": 200})
types = {}
for t in results:
    ut = t.get("upload_type", "unknown")
    types[ut] = types.get(ut, 0) + 1
for k, v in sorted(types.items(), key=lambda x: -x[1]):
    print(f"  {v:3d}  {k}")

# 5. License distribution across 200 tracks
print("\n=== License distribution (200 tracks) ===")
lics = {}
for t in results:
    l = t.get("license_name", "unknown")
    lics[l] = lics.get(l, 0) + 1
for k, v in sorted(lics.items(), key=lambda x: -x[1]):
    print(f"  {v:3d}  {k}")

# 6. Tags / genre fields
print("\n=== Tag samples (10 tracks) ===")
results = fetch({"limit": 10})
for t in results:
    tags = t.get("upload_tags", "")
    extra = t.get("upload_extra", {})
    usertags = extra.get("usertags", "") if isinstance(extra, dict) else ""
    print(f"  {t.get('upload_name','?')[:35]:<35}  tags={tags[:60]}")
    print(f"  {'':35}  usertags={usertags[:60]}")
