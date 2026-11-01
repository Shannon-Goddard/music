import csv, re

# Match any actual non-ASCII character in the URL (codepoint > 127)
NON_ASCII_CHAR_RE = re.compile(r'[^\x00-\x7F]')

samples = []
total = bad = 0

with open("scripts/catalog_review.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        url = row["stream_url"]
        total += 1
        if NON_ASCII_CHAR_RE.search(url):
            bad += 1
            if len(samples) < 10:
                samples.append(url)

with open("scripts/url_sample.txt", "w", encoding="utf-8") as out:
    out.write(f"TOTAL: {total:,}  BAD (actual non-ASCII chars in URL): {bad:,}  ({bad/total*100:.1f}%)\n\n")
    for u in samples:
        out.write(u + "\n\n")

print("Done -> scripts/url_sample.txt")
