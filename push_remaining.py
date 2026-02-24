import requests, time, json

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'

# Wait for any running classification to finish
for i in range(30):
    time.sleep(5)
    p = requests.get(f'{API}/api/classify/progress?week=2026-W09', timeout=30).json()
    running = p.get('running', False)
    done = p.get('done', 0)
    total = p.get('total', 0)
    print(f'W09 classify: {done}/{total} running={running}', flush=True)
    if not running:
        print('W09 classification done!', flush=True)
        break

# Push W08
time.sleep(5)
with open('events_cache/2026-W08.json') as f:
    data = json.load(f)
events = [{'agent': e['agent_name'], 'title': e['title'], 'start': e['start_time'], 
           'end': e.get('end_time',''), 'description': e.get('description',''), 
           'location': e.get('location','')} for e in data]
r = requests.post(f'{API}/api/sync', json={'week': '2026-W08', 'events': events, 'api_key': KEY}, timeout=120)
print(f'W08 sync: {r.status_code} {r.text[:80]}', flush=True)

# Classify W08 and wait
time.sleep(3)
r = requests.post(f'{API}/api/classify', json={'week': '2026-W08'}, timeout=30)
print(f'W08 classify start: {r.status_code} {r.text[:80]}', flush=True)

for i in range(60):
    time.sleep(5)
    p = requests.get(f'{API}/api/classify/progress?week=2026-W08', timeout=30).json()
    running = p.get('running', False)
    done = p.get('done', 0)
    total = p.get('total', 0)
    print(f'W08 classify: {done}/{total} running={running}', flush=True)
    if not running and i > 2:
        break

# Push W10
time.sleep(5)
with open('events_cache/2026-W10.json') as f:
    data = json.load(f)
events = [{'agent': e['agent_name'], 'title': e['title'], 'start': e['start_time'], 
           'end': e.get('end_time',''), 'description': e.get('description',''), 
           'location': e.get('location','')} for e in data]
r = requests.post(f'{API}/api/sync', json={'week': '2026-W10', 'events': events, 'api_key': KEY}, timeout=120)
print(f'W10 sync: {r.status_code} {r.text[:80]}', flush=True)

# Classify W10 and wait
time.sleep(3)
r = requests.post(f'{API}/api/classify', json={'week': '2026-W10'}, timeout=30)
print(f'W10 classify start: {r.status_code} {r.text[:80]}', flush=True)

for i in range(60):
    time.sleep(5)
    p = requests.get(f'{API}/api/classify/progress?week=2026-W10', timeout=30).json()
    running = p.get('running', False)
    done = p.get('done', 0)
    total = p.get('total', 0)
    print(f'W10 classify: {done}/{total} running={running}', flush=True)
    if not running and i > 2:
        break

# Final
print('\n=== FINAL ===', flush=True)
for wk in ['2026-W08', '2026-W09', '2026-W10']:
    r = requests.get(f'{API}/api/status?week={wk}', timeout=30)
    print(f'{wk}: {r.text}', flush=True)
