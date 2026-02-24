import json, requests, time

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'

# Push all 3 weeks, then classify each SEQUENTIALLY
for wk in ['2026-W08', '2026-W09', '2026-W10']:
    print(f'\n=== {wk} ===', flush=True)
    with open(f'events_cache/{wk}.json') as f:
        data = json.load(f)
    events = [{'agent': e['agent_name'], 'title': e['title'], 'start': e['start_time'], 
               'end': e.get('end_time',''), 'description': e.get('description',''), 
               'location': e.get('location','')} for e in data]
    
    # Sync
    r = requests.post(f'{API}/api/sync', json={'week': wk, 'events': events, 'api_key': KEY}, timeout=120)
    print(f'Sync: {r.status_code} {r.text[:100]}', flush=True)
    if r.status_code != 200:
        print('SYNC FAILED, waiting 10s and retrying...', flush=True)
        time.sleep(10)
        r = requests.post(f'{API}/api/sync', json={'week': wk, 'events': events, 'api_key': KEY}, timeout=120)
        print(f'Retry: {r.status_code} {r.text[:100]}', flush=True)
    
    # Classify
    time.sleep(3)
    r = requests.post(f'{API}/api/classify', json={'week': wk}, timeout=30)
    print(f'Classify: {r.status_code} {r.text[:100]}', flush=True)
    
    # Wait for completion
    for i in range(60):
        time.sleep(3)
        p = requests.get(f'{API}/api/classify/progress?week={wk}', timeout=30).json()
        done = p.get('done', 0)
        total = p.get('total', 0)
        running = p.get('running', False)
        print(f'  {done}/{total} running={running}', flush=True)
        if not running and i > 0:
            break
    
    time.sleep(5)

# Final status
print('\n=== FINAL STATUS ===', flush=True)
for wk in ['2026-W08', '2026-W09', '2026-W10']:
    r = requests.get(f'{API}/api/status?week={wk}', timeout=30)
    print(f'{wk}: {r.text}', flush=True)
