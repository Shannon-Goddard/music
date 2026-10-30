import sys
sys.path.insert(0, 'backend')
import logging
logging.basicConfig(level=logging.WARNING)
from ingestion.ia_adapter import IAAdapter

adapter = IAAdapter()
for col in ['netlabels', '78rpm']:
    records = adapter.fetch(0, col)
    print(f'\n--- {col} (page 0, {len(records)} records) ---')
    for r in records[:8]:
        creator = r.get('creator', 'Unknown')
        if isinstance(creator, list): creator = creator[0]
        subj = r.get('subject', [])
        if isinstance(subj, list): subj = subj[:2]
        title = str(r.get('title', '')).encode('ascii', 'replace').decode()
        creator = str(creator).encode('ascii', 'replace').decode()
        print(f'  {title[:50]} | {creator[:25]} | {subj}')
