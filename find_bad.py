import json, requests

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'

def clean(v):
    if isinstance(v, str) and len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1]
    return v

with open('events_cache/2026-W08.json') as f:
    data = json.load(f)

# Test first 50 one by one
for i, e in enumerate(data[:50]):
    ev = {
        'agent': clean(e['agent_name']),
        'title': clean(e['title']),
        'start': clean(e['start_time']),
        'end': clean(e.get('end_time', '')),
        'description': clean(e.get('description', '')),
        'location': clean(e.get('location', ''))
    }
    r = requests.post(f'{API}/api/sync', json={'week': '2026-W08', 'events': [ev], 'api_key': KEY}, timeout=30)
    if r.status_code != 200:
        print(f'BAD event #{i}: {r.status_code}', flush=True)
        print(f'  agent={ev["agent"]} title={ev["title"][:50]}', flush=True)
        print(f'  response={r.text[:100]}', flush=True)
        break
    else:
        print(f'OK #{i}: {ev["agent"][:20]} - {ev["title"][:30]}', flush=True)
