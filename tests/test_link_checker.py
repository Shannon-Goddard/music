import sys
sys.path.insert(0, 'backend')
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

from health.link_checker import run

print("Running link health check against all active tracks...\n")
results = run(limit=100)

print(f"\nSummary:")
print(f"  Alive:           {results['alive']}")
print(f"  Dead links:      {results['dead']}")
print(f"  Pending recheck: {results['pending_recheck']}")
print(f"  Errors:          {results['errors']}")
