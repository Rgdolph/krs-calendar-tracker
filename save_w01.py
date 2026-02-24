import json, sys

# Read from stdin
data = json.load(sys.stdin)
events = data if isinstance(data, list) else data.get('events', [])

with open('events_cache/2026-W01.json', 'w') as f:
    json.dump(events, f)
print(f"Saved {len(events)} events")
