"""Read a JSON file path from stdin and save the compact version."""
import json, sys

wk = sys.argv[1]
data = json.loads(sys.stdin.read())
events = data.get('events', data) if isinstance(data, dict) else data
compact = [{'a': e.get('agent',''), 't': e.get('title',''), 's': e.get('start',''), 'n': e.get('end',''), 'd': (e.get('description','') or '')[:100], 'l': (e.get('location','') or '')[:100]} for e in events]
with open(f'events_cache/{wk}.json', 'w') as f:
    json.dump(compact, f)
print(f'{wk}: saved {len(compact)} events')
