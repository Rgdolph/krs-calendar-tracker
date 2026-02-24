"""Push cached week JSON files to the cloud. Run after browser fetches them."""
import json, requests, time, sys, os

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'

def push_events(wk, events):
    synced = 0
    formatted = [{
        'agent': e.get('agent', ''),
        'title': e.get('title', ''),
        'start': e.get('start', ''),
        'end': e.get('end', ''),
        'description': e.get('description', ''),
        'location': e.get('location', '')
    } for e in events]
    for i in range(0, len(formatted), 25):
        chunk = formatted[i:i+25]
        for attempt in range(5):
            try:
                r = requests.post(f'{API}/api/sync', json={'week': wk, 'events': chunk, 'api_key': KEY}, timeout=120)
                if r.status_code == 200:
                    synced += len(chunk)
                    break
                print(f'  {wk} chunk@{i} attempt {attempt+1}: HTTP {r.status_code}', flush=True)
            except Exception as e:
                print(f'  {wk} chunk@{i} attempt {attempt+1}: {e}', flush=True)
            time.sleep(10 * (attempt + 1))
        time.sleep(3)
    print(f'  {wk}: pushed {synced}/{len(formatted)}', flush=True)
    return synced

# Push all cached weeks
for w in range(1, 8):
    wk = f'2026-W{w:02d}'
    path = f'events_cache/{wk}.json'
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
        events = data.get('events', data) if isinstance(data, dict) else data
        print(f'{wk}: {len(events)} events', flush=True)
        push_events(wk, events)
    else:
        print(f'{wk}: no cache file', flush=True)
