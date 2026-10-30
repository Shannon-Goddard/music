"""
Probe FMA for any live API endpoints.
Run: python scripts/probe_fma.py
"""
import requests

BASE = "https://freemusicarchive.org"
HEADERS = {"User-Agent": "Mozilla/5.0"}

endpoints = [
    # Old v1 API
    "/api/get/tracks.json?limit=3",
    "/api/get/albums.json?limit=3",
    "/api/get/artists.json?limit=3",
    "/api/get/genres.json?limit=3",
    # Possible v2
    "/api/v2/tracks?limit=3",
    "/api/v2/albums?limit=3",
    "/api/tracks?limit=3",
    # JSON endpoints that might back the SPA
    "/api/tracks.json?limit=3",
    "/music.json?limit=3",
    # Genre browse — might return JSON with Accept header
    "/genres.json",
    "/music/charts/all.json",
]

for path in endpoints:
    try:
        r = requests.get(BASE + path, headers={**HEADERS, "Accept": "application/json"}, timeout=10)
        ct = r.headers.get("Content-Type", "")
        preview = r.text[:120].replace("\n", " ")
        print(f"  {r.status_code}  {path}")
        print(f"       ct={ct[:50]}  body={preview}")
    except Exception as e:
        print(f"  ERR  {path}  {e}")
