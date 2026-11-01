"""
Audit rows with non-ASCII in text fields.
Distinguishes clean Unicode (real Arabic, French, etc.)
from mojibake (UTF-8 read as Latin-1, producing Ø£Ù†ÙˆØ§Ø± patterns).
"""
import csv, re, unicodedata

# Mojibake signature: Latin-1 misread of UTF-8 Arabic/Cyrillic
# Produces characters in the U+00C0–U+00FF + U+2013–U+201D range in dense runs
MOJIBAKE_RE = re.compile(r'[\xc0-\xff\u2013\u2014\u2018\u2019\u201c\u201d\u00f9\u00f8]{3,}')

def is_mojibake(text: str) -> bool:
    return bool(MOJIBAKE_RE.search(text or ""))

def has_non_ascii(text: str) -> bool:
    return any(ord(c) > 127 for c in (text or ""))

total = mojibake = clean_non_ascii = ascii_only = 0
mojibake_by_lang = {}
samples_mojibake = []
samples_clean_non_ascii = []

with open("cleaning/catalog_clean_stream_url.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        check = " ".join([row["title"], row["artist_name"], row["attribution_text"]])
        total += 1
        if is_mojibake(check):
            mojibake += 1
            lang = row["language"] or "none"
            mojibake_by_lang[lang] = mojibake_by_lang.get(lang, 0) + 1
            if len(samples_mojibake) < 5:
                samples_mojibake.append({
                    "lang": row["language"],
                    "title": row["title"],
                    "artist": row["artist_name"],
                    "platform": row["source_platform"],
                    "content_type": row["content_type"],
                })
        elif has_non_ascii(check):
            clean_non_ascii += 1
            if len(samples_clean_non_ascii) < 5:
                samples_clean_non_ascii.append({
                    "lang": row["language"],
                    "title": row["title"],
                    "artist": row["artist_name"],
                    "platform": row["source_platform"],
                })
        else:
            ascii_only += 1

with open("cleaning/mojibake_audit.txt", "w", encoding="utf-8") as out:
    out.write(f"TOTAL: {total:,}\n")
    out.write(f"  ASCII only (clean):        {ascii_only:>7,}  ({ascii_only/total*100:.1f}%)\n")
    out.write(f"  Clean Unicode (real text): {clean_non_ascii:>7,}  ({clean_non_ascii/total*100:.1f}%)\n")
    out.write(f"  Mojibake (broken encoding):{mojibake:>7,}  ({mojibake/total*100:.1f}%)\n")

    out.write("\n--- MOJIBAKE BY LANGUAGE ---\n")
    for lang, count in sorted(mojibake_by_lang.items(), key=lambda x: -x[1]):
        out.write(f"  {lang:<10} {count:>6,}\n")

    out.write("\n--- MOJIBAKE SAMPLES ---\n")
    for s in samples_mojibake:
        out.write(f"  lang={s['lang']}  platform={s['platform']}  type={s['content_type']}\n")
        out.write(f"  title:  {s['title']}\n")
        out.write(f"  artist: {s['artist']}\n\n")

    out.write("\n--- CLEAN NON-ASCII SAMPLES (would survive) ---\n")
    for s in samples_clean_non_ascii:
        out.write(f"  lang={s['lang']}  platform={s['platform']}\n")
        out.write(f"  title:  {s['title']}\n")
        out.write(f"  artist: {s['artist']}\n\n")

print("Done -> cleaning/mojibake_audit.txt")
