import requests

CLIENT_ID = 'f15a1ec3'
TAGS = ['electronic', 'rock', 'ambient', 'experimental', 'blues', 'jazz',
        'industrial', 'classical', 'hiphop', 'folk']

for tag in TAGS:
    r = requests.get('https://api.jamendo.com/v3.0/tracks/', params={
        'client_id': CLIENT_ID, 'format': 'json',
        'limit': 1, 'tags': tag,
    }, timeout=10)
    data = r.json()
    h = data.get('headers', {})
    print(f"{tag:15s}  results_count={h.get('results_count','?')}  fullcount={h.get('results_fullcount','?')}  keys={list(h.keys())}")
    if not h:
        print(f"  raw headers: {data.get('headers')}  top keys: {list(data.keys())}")
