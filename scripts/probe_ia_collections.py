import requests, json

# Known large IA audio collections worth probing
CANDIDATES = [
    "audio_music",
    "audio",
    "netlabels",
    "78rpm",
    "georgeblood",
    "librivoxaudio",
    "opensource_audio",
    "etree",
    "audio_bookspoetry",
    "podcasts",
    "radio_programs",
    "audio_religion",
    "audio_tech",
    "audio_foreign",
    "folkways",
    "audio_news",
    "live_music_archive",
    "GratefulDead",
    "PhilLesh",
    "audio_comedy",
]

results = []
for col in CANDIDATES:
    try:
        resp = requests.get(
            "https://archive.org/advancedsearch.php",
            params={
                "q": f"collection:{col} AND mediatype:audio",
                "rows": 1,
                "output": "json",
                "fl[]": "identifier",
            },
            timeout=10,
        )
        count = resp.json()["response"]["numFound"]
        results.append((count, col))
        print(f"{count:>8}  {col}")
    except Exception as e:
        print(f"       ?  {col}  ERROR: {e}")

results.sort(reverse=True)
print("\n--- SORTED ---")
for count, col in results:
    print(f"{count:>8}  {col}")
