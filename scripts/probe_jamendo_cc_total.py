"""
Find total CC-licensed tracks on Jamendo and map all productive tags.
Run: python scripts/probe_jamendo_cc_total.py
"""
import requests, time

CLIENT_ID = "f15a1ec3"
BASE = "https://api.jamendo.com/v3.0/tracks/"

# Every tag worth trying — broad net
CANDIDATE_TAGS = [
    # Electronic
    "electronic", "ambient", "chillwave", "lounge", "house", "techno",
    "trance", "dance", "disco", "downtempo", "idm", "synthpop", "newwave",
    "darkambient", "spaceambient", "drumnbass", "dubstep", "garage",
    # Rock
    "alternativerock", "hardrock", "classicrock", "progressiverock",
    "softrock", "metal", "rock", "indierock", "punkrock", "grunge",
    "heavymetal", "deathmetal", "blackmetal", "postrock",
    # Pop / urban
    "pop", "soul", "hiphop", "blues", "reggae", "rnb", "funk",
    "gospel", "latin", "ska", "dancehall",
    # Acoustic / folk / world
    "acoustic", "folk", "world", "jazz", "classical", "country",
    "bluegrass", "celtic", "flamenco", "bossanova", "afrobeat",
    # Cinematic / instrumental
    "cinematic", "orchestral", "neoclassical", "soundtrack", "videogame",
    "score", "filmscore",
    # Misc
    "experimental", "noise", "spoken", "comedy", "children",
]


def depth(tag):
    """Return total tracks available for a tag (paginate until empty)."""
    total = 0
    for page in range(50):  # cap at 50 pages = 10,000 per tag
        r = requests.get(BASE, params={
            "client_id": CLIENT_ID, "format": "json", "limit": 200,
            "audioformat": "mp32", "order": "releasedate_desc",
            "tags": tag, "offset": page * 200,
        }, timeout=15)
        n = r.json()["headers"]["results_count"]
        total += n
        if n < 200:
            break
        time.sleep(0.1)
    return total


print(f"{'TAG':<22} {'TRACKS':>8}")
print("-" * 32)
productive = {}
for tag in CANDIDATE_TAGS:
    n = depth(tag)
    if n > 0:
        productive[tag] = n
        print(f"  {tag:<20} {n:>8}")
    else:
        print(f"  {tag:<20} {'---':>8}")

print()
print(f"Productive tags: {len(productive)}")
print(f"Sum across tags (with dupes): {sum(productive.values()):,}")
print(f"\nTop 20 by depth:")
for tag, n in sorted(productive.items(), key=lambda x: -x[1])[:20]:
    print(f"  {tag:<22} {n:>8,}")
