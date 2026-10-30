"""
Probe Jamendo's full genre/tag taxonomy.

Sweeps /tracks with musicinfo across many pages, collects every genre,
vartag, and instrument label actually used, counts frequency, and dumps
a sorted report so we can build an informed tag mapping.

Usage:
  python -u scripts/probe_jamendo_taxonomy.py
  python -u scripts/probe_jamendo_taxonomy.py --pages 50   # deeper sweep
"""
import sys, os, argparse, json, time, logging
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import boto3
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

API      = 'https://api.jamendo.com/v3.0/tracks/'
PAGE     = 200


def get_client_id():
    c = boto3.client('secretsmanager', region_name='us-east-1')
    return json.loads(c.get_secret_value(SecretId='music/jamendo')['SecretString'])['client_id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=100,
                        help='Number of pages to sweep (default 100 = 20k tracks)')
    args = parser.parse_args()

    cid = get_client_id()
    genres     = Counter()
    vartags    = Counter()
    instruments = Counter()

    for page in range(args.pages):
        try:
            r = requests.get(API, params={
                'client_id': cid, 'format': 'json',
                'limit': PAGE, 'offset': page * PAGE,
                'include': 'musicinfo',
                'order': 'popularity_total',   # popularity sweep = broad coverage
            }, timeout=15)
            r.raise_for_status()
            results = r.json().get('results', [])
        except Exception as e:
            logger.warning('page %d error: %s', page, e)
            time.sleep(2)
            continue

        if not results:
            logger.info('No more results at page %d', page)
            break

        for track in results:
            mi = track.get('musicinfo') or {}
            tags = mi.get('tags') or {}
            for g in tags.get('genres') or []:
                genres[g.lower()] += 1
            for v in tags.get('vartags') or []:
                vartags[v.lower()] += 1
            for i in tags.get('instruments') or []:
                instruments[i.lower()] += 1

        if page % 10 == 0:
            logger.info('page %d — unique genres=%d  vartags=%d  instruments=%d',
                        page, len(genres), len(vartags), len(instruments))
        time.sleep(0.3)

    # Print full report
    print('\n' + '='*60)
    print(f'GENRES ({len(genres)} unique)')
    print('='*60)
    for tag, count in genres.most_common():
        print(f'  {count:>6}  {tag}')

    print('\n' + '='*60)
    print(f'VARTAGS ({len(vartags)} unique)')
    print('='*60)
    for tag, count in vartags.most_common():
        print(f'  {count:>6}  {tag}')

    print('\n' + '='*60)
    print(f'INSTRUMENTS ({len(instruments)} unique)')
    print('='*60)
    for tag, count in instruments.most_common():
        print(f'  {count:>6}  {tag}')

    # Save raw JSON for reference
    out = {
        'genres':      dict(genres.most_common()),
        'vartags':     dict(vartags.most_common()),
        'instruments': dict(instruments.most_common()),
    }
    out_path = os.path.join(os.path.dirname(__file__), 'jamendo_taxonomy.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    logger.info('Saved to %s', out_path)


if __name__ == '__main__':
    main()
