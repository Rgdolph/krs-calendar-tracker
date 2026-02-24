"""Push cached week JSON files to Render, then classify. Robust retries."""
import json, requests, time, sys, os

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'

def push_week(wk, events):
    formatted = []
    for e in events:
        formatted.append({
            'agent': e.get('a', e.get('agent', '')),
            'title': e.get('t', e.get('title', '')),
            'start': e.get('s', e.get('start', '')),
            'end': e.get('n', e.get('end', '')),
            'description': (e.get('d', e.get('description', '')) or '')[:100],
            'location': (e.get('l', e.get('location', '')) or '')[:100]
        })
    synced = 0
    for i in range(0, len(formatted), 25):
        chunk = formatted[i:i+25]
        for attempt in range(5):
            try:
                r = requests.post(f'{API}/api/sync', json={'week': wk, 'events': chunk, 'api_key': KEY}, timeout=180)
                if r.status_code == 200:
                    synced += len(chunk)
                    print(f'  {wk}: chunk {i//25+1} ok ({synced}/{len(formatted)})', flush=True)
                    break
                print(f'  {wk}: chunk {i//25+1} HTTP {r.status_code}, retry {attempt+1}', flush=True)
            except Exception as ex:
                print(f'  {wk}: chunk {i//25+1} error: {ex}, retry {attempt+1}', flush=True)
            time.sleep(15 * (attempt + 1))
        time.sleep(2)
    return synced

def classify_week(wk):
    try:
        s = requests.get(f'{API}/api/status?week={wk}', timeout=120).json()
        unc = s.get('unclassified', 0)
        if unc == 0:
            print(f'  {wk}: all classified ({s["total"]} total, {s["sales"]} sales)', flush=True)
            return
        print(f'  {wk}: classifying {unc}...', flush=True)
        requests.post(f'{API}/api/classify', json={'week': wk}, headers={'X-API-Key': KEY}, timeout=30)
        for i in range(120):
            time.sleep(5)
            try:
                p = requests.get(f'{API}/api/classify/progress?week={wk}', timeout=30).json()
                if not p.get('running', False) and i > 3:
                    break
            except:
                pass
        s2 = requests.get(f'{API}/api/status?week={wk}', timeout=120).json()
        print(f'  {wk}: done - {s2["total"]} total, {s2["sales"]} sales, {s2.get("unclassified",0)} remaining', flush=True)
    except Exception as e:
        print(f'  {wk}: classify error: {e}', flush=True)

weeks = sys.argv[1:] if len(sys.argv) > 1 else [f'2026-W{i:02d}' for i in range(1, 8)]

# Wake app
print('Waking app...', flush=True)
for i in range(10):
    try:
        if requests.get(f'{API}/', timeout=120).status_code == 200:
            print('App ready!', flush=True)
            break
    except: pass
    time.sleep(10)

for wk in weeks:
    cache = f'events_cache/{wk}.json'
    if not os.path.exists(cache):
        print(f'{wk}: no cache file, skipping', flush=True)
        continue
    with open(cache) as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = events.get('events', [])
    print(f'{wk}: {len(events)} events from cache', flush=True)
    push_week(wk, events)
    time.sleep(3)

print('\n=== CLASSIFYING ===', flush=True)
for wk in weeks:
    classify_week(wk)
    time.sleep(3)

print('\n=== FINAL STATUS ===', flush=True)
for w in range(1, 11):
    wk = f'2026-W{w:02d}'
    try:
        d = requests.get(f'{API}/api/status?week={wk}', timeout=120).json()
        print(f'{wk}: {d["total"]} events, {d["sales"]} sales, {d.get("unclassified",0)} unclassified', flush=True)
    except:
        pass
