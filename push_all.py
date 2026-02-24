import json, requests, time

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'

for wk in ['2026-W08', '2026-W09', '2026-W10']:
    with open(f'events_cache/{wk}.json') as f:
        data = json.load(f)
    events = [{'agent': e['agent_name'], 'title': e['title'], 'start': e['start_time'], 
               'end': e.get('end_time',''), 'description': e.get('description',''), 
               'location': e.get('location','')} for e in data]
    r = requests.post(f'{API}/api/sync', json={'week': wk, 'events': events, 'api_key': KEY}, timeout=120)
    print(f'{wk}: {r.status_code} {r.text[:100]}', flush=True)
    time.sleep(2)

# Now classify all 3
for wk in ['2026-W08', '2026-W09', '2026-W10']:
    r = requests.post(f'{API}/api/classify', json={'week': wk}, timeout=30)
    print(f'Classify {wk}: {r.status_code} {r.text[:100]}', flush=True)
    # Wait for classification to finish
    for i in range(30):
        time.sleep(3)
        p = requests.get(f'{API}/api/classify/progress?week={wk}', timeout=30).json()
        done = p.get('done', 0)
        total = p.get('total', 0)
        running = p.get('running', False)
        print(f'  {wk}: {done}/{total} running={running}', flush=True)
        if not running:
            break
    print(flush=True)

# Final status
for wk in ['2026-W08', '2026-W09', '2026-W10']:
    r = requests.get(f'{API}/api/status?week={wk}', timeout=30)
    print(f'{wk} final: {r.text}', flush=True)
