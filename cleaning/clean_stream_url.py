"""
Writes catalog_clean_stream_url.csv — same as catalog_review.csv but with rows
removed where stream_url contains non-ASCII characters in the URL path.

Two tiers removed:
  - Non-Latin scripts (Bengali, Devanagari, Arabic, CJK, etc.) — definitely broken
  - Accented Latin (é, ô, ü, etc.) — unreliable across players/proxies

Run: python scripts/clean_stream_url.py
"""
import csv
import re
from urllib.parse import urlparse

# Any non-ASCII character in the URL path segment
NON_ASCII_RE = re.compile(r'[^\x00-\x7F]')

IN_FILE  = "cleaning/catalog_review.csv"
OUT_FILE = "cleaning/catalog_clean_stream_url.csv"


def has_bad_url(url: str) -> bool:
    if not url:
        return False
    path = urlparse(url).path
    return bool(NON_ASCII_RE.search(path))


def main():
    kept = removed = 0

    with open(IN_FILE, encoding="utf-8") as fin, \
         open(OUT_FILE, "w", newline="", encoding="utf-8") as fout:

        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            if has_bad_url(row["stream_url"]):
                removed += 1
            else:
                writer.writerow(row)
                kept += 1

    print(f"Removed : {removed:,}")
    print(f"Kept    : {kept:,}")
    print(f"Output  : {OUT_FILE}")


if __name__ == "__main__":
    main()
