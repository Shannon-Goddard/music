import sys, requests, json
sys.path.insert(0, 'backend')
from ingestion.ia_adapter import IA_COLLECTIONS

# Check language field presence and values across collections
for col, query in IA_COLLECTIONS.items():
    resp = requests.get('https://archive.org/advancedsearch.php', params={
        'q': query,
        'fl[]': ['identifier', 'language', 'title'],
        'rows': 10, 'page': 1, 'output': 'json'
    }, timeout=15)
    docs = resp.json()['response']['docs']
    langs = [d.get('language', 'MISSING') for d in docs]
    print(f'{col}: {langs}')
    sys.stdout.flush()
