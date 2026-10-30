"""
Probe Internet Archive's full genre/subject taxonomy across audio collections.

Sweeps IA advanced search across all our target collections, collects every
subject tag, counts frequency, and dumps a sorted report so we can build
an informed genre mapping before ingesting.

Usage:
  python -u scripts/probe_ia_taxonomy.py
  python -u scripts/probe_ia_taxonomy.py --pages 50  # deeper sweep
"""
import sys, os, argparse, json, time, logging
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

IA_SEARCH = 'https://archive.org/advancedsearch.php'
PAGE_SIZE  = 100

# All collections we ingest from
COLLECTIONS = [
    'netlabels',
    'opensource_audio',
    'audio_music',
    'georgeblood',
]

# Base query per collection (same as ia_adapter.py)
QUERIES = {
    'netlabels':       'mediatype:audio AND collection:netlabels AND licenseurl:(*creativecommons* OR *publicdomain*)',
    'opensource_audio':'mediatype:audio AND collection:opensource_audio AND licenseurl:(*creativecommons* OR *publicdomain*)',
    'audio_music':     'mediatype:audio AND collection:audio_music AND licenseurl:(*creativecommons* OR *publicdomain*)',
    'georgeblood':     'mediatype:audio AND collection:georgeblood',
}


def probe_collection(name: str, query: str, pages: int) -> Counter:
    subjects = Counter()
    for page in range(pages):
        try:
            r = requests.get(IA_SEARCH, params={
                'q':       query,
                'fl[]':    ['subject'],
                'rows':    PAGE_SIZE,
                'page':    page + 1,
                'output':  'json',
            }, timeout=20)
            r.raise_for_status()
            docs = r.json().get('response', {}).get('docs', [])
        except Exception as e:
            logger.warning('[%s] page %d error: %s', name, page, e)
            time.sleep(2)
            continue

        if not docs:
            logger.info('[%s] exhausted at page %d', name, page)
            break

        for doc in docs:
            raw = doc.get('subject', [])
            if isinstance(raw, str):
                raw = [raw]
            for s in (raw or []):
                for part in s.replace(';', ',').split(','):
                    tag = part.strip().lower()
                    if tag:
                        subjects[tag] += 1

        if page % 10 == 0:
            logger.info('[%s] page %d — %d unique tags so far', name, page, len(subjects))
        time.sleep(0.5)

    return subjects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=50,
                        help='Pages per collection (default 50 = 5k items each)')
    args = parser.parse_args()

    all_subjects = Counter()
    per_collection = {}

    for name, query in QUERIES.items():
        logger.info('=== Probing collection: %s ===', name)
        counts = probe_collection(name, query, args.pages)
        per_collection[name] = dict(counts.most_common(100))
        all_subjects.update(counts)
        logger.info('[%s] done — %d unique tags', name, len(counts))
        time.sleep(1)

    # Print combined report — top 200
    print('\n' + '='*60)
    print(f'ALL COLLECTIONS COMBINED — top 200 subject tags')
    print('='*60)
    for tag, count in all_subjects.most_common(200):
        print(f'  {count:>6}  {tag}')

    # Save full JSON
    out = {
        'combined':       dict(all_subjects.most_common()),
        'per_collection': per_collection,
    }
    out_path = os.path.join(os.path.dirname(__file__), 'ia_taxonomy.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    logger.info('Saved to %s', out_path)


if __name__ == '__main__':
    main()
