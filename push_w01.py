import json, requests, time, sys
sys.path.insert(0, '.')
from save_and_push import push_week

# W01 data already fetched from browser
raw = json.loads(open('w01_raw.json').read())
events = raw.get('events', raw) if isinstance(raw, dict) else raw

# Save
with open('events_cache/2026-W01.json', 'w') as f:
    json.dump(events, f)
print(f"Saved {len(events)} events")

push_week("2026-W01", events)
