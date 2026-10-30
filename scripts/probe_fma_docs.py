"""
Scrape FMA for any current API docs, dataset links, or developer access.
Run: python scripts/probe_fma_docs.py
"""
import requests, re
from html.parser import HTMLParser

HEADERS = {"User-Agent": "Mozilla/5.0"}

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer"):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer"):
            self._skip = False
    def handle_data(self, data):
        if not self._skip and data.strip():
            self.text.append(data.strip())

def scrape(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    p = TextExtractor()
    p.feed(r.text)
    # Also pull all hrefs
    links = re.findall(r'href=["\']([^"\']+)["\']', r.text)
    api_links = [l for l in links if any(k in l.lower() for k in ["api", "dataset", "download", "developer", "data"])]
    return " ".join(p.text), api_links

for url in [
    "https://freemusicarchive.org/app-developers",
    "https://freemusicarchive.org/about/",
]:
    print(f"\n=== {url} ===")
    text, links = scrape(url)
    # Print first 2000 chars of text content
    print(text[:2000])
    if links:
        print("\n--- Relevant links ---")
        for l in set(links):
            print(f"  {l}")
