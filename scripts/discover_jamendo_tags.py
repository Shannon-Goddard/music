"""
Discover real Jamendo genre tag names by:
1. Sampling unfiltered pages (releasedate_desc)
2. Probing each of our current JAMENDO_TAGS to see which return 0 results
3. Trying known alternate spellings for the zero-result tags
Run: python scripts/discover_jamendo_tags.py
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

CLIENT_ID = "f15a1ec3"
BASE = "https://api.jamendo.com/v3.0/tracks/"

CURRENT_TAGS = [
    "electronic", "ambient", "pop", "rock", "jazz", "classical",
    "folk", "hiphop", "metal", "blues", "soul", "reggae",
    "chillwave", "dance", "acoustic", "instrumental", "lounge",
    "experimental", "soundtrack", "world",
]

# Candidate alternates for the zero-result tags
ALTERNATES = {
    "ambient":       ["ambient", "ambientelectronic", "darkambient", "spaceambient", "newage"],
    "rock":          ["rock", "alternativerock", "indierock", "hardrock", "classicrock", "softrock", "progressiverock"],
    "jazz":          ["jazz", "jazzfusion", "smoothjazz", "bossanova", "swing", "bebop"],
    "chillwave":     ["chillwave", "chillout", "chill", "chilledelectronic", "downtempo", "triphop"],
    "dance":         ["dance", "edm", "clubdance", "eurodance", "disco", "house", "techno", "trance"],
    "instrumental":  ["instrumental", "cinematic", "orchestral", "neoclassical"],
    "soundtrack":    ["soundtrack", "filmscore", "score", "cinematic", "videogame"],
}


def probe(tag, pages=1):
    """Return total tracks fetched for a tag across `pages` pages."""
    total = 0
    for page in range(pages):
        r = requests.get(BASE, params={
            "client_id": CLIENT_ID, "format": "json", "limit": 200,
            "include": "musicinfo", "audioformat": "mp32",
            "order": "releasedate_desc", "tags": tag,
            "offset": page * 200,
        }, timeout=15)
        results = r.json().get("results", [])
        total += len(results)
        if len(results) < 200:
            break
    return total


def collect_genre_tags(pages=5):
    """Sample unfiltered pages and collect all genre tags that appear."""
    counts = collections.Counter()
    for page in range(pages):
        r = requests.get(BASE, params={
            "client_id": CLIENT_ID, "format": "json", "limit": 200,
            "include": "musicinfo", "audioformat": "mp32",
            "order": "releasedate_desc", "offset": page * 200,
        }, timeout=15)
        results = r.json().get("results", [])
        if not results:
            break
        for t in results:
            mi = t.get("musicinfo") or {}
            for g in (mi.get("tags") or {}).get("genres", []):
                counts[g] += 1
    return counts


print("=" * 60)
print("STEP 1: Genre tags found in unfiltered sample (5 pages)")
print("=" * 60)
counts = collect_genre_tags(5)
print(f"Unique genre tags: {len(counts)}")
for tag, n in counts.most_common():
    print(f"  {n:4d}  {tag}")

print()
print("=" * 60)
print("STEP 2: Probe current JAMENDO_TAGS — which return 0?")
print("=" * 60)
zero_tags = []
for tag in CURRENT_TAGS:
    n = probe(tag, pages=1)
    status = "OK" if n > 0 else "ZERO"
    print(f"  {status:4s}  {tag:20s}  ({n} tracks)")
    if n == 0:
        zero_tags.append(tag)

print()
print("=" * 60)
print("STEP 3: Probe alternates for zero-result tags")
print("=" * 60)
replacements = {}
for tag in zero_tags:
    alts = ALTERNATES.get(tag, [])
    print(f"\n  [{tag}] — trying alternates:")
    best = []
    for alt in alts:
        n = probe(alt, pages=1)
        print(f"    {n:4d}  {alt}")
        if n > 0:
            best.append((n, alt))
    best.sort(reverse=True)
    if best:
        replacements[tag] = [a for _, a in best]
        print(f"    => best replacements: {replacements[tag]}")
    else:
        print(f"    => no working alternates found")

print()
print("=" * 60)
print("SUMMARY — suggested JAMENDO_TAGS update")
print("=" * 60)
final = []
for tag in CURRENT_TAGS:
    if tag not in zero_tags:
        final.append(tag)
    else:
        reps = replacements.get(tag, [])
        if reps:
            final.extend(reps)
            print(f"  REPLACE  {tag}  =>  {reps}")
        else:
            print(f"  DROP     {tag}  (no working alternate)")

print()
print("Final tag list:")
print(json.dumps(sorted(set(final)), indent=2))
