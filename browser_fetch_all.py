"""
Fetch weeks W01-W07 via browser automation and push to Render.
Uses Playwright CDP to connect to the OpenClaw browser.
"""
import json, requests, time, os, sys
from datetime import date, timedelta

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'
SCRIPT = 'https://script.google.com/a/macros/krs.insure/s/AKfycbwN46cLo1aqtgwYz6CBAig_WOaBM2x1MTlYkcDbuXrejwAFfRfWgXazG_Qo3Yn0s2Ekzw/exec'

WEEKS = [
    ('2026-W01', '2025-12-29', '2026-01-04'),
    ('2026-W02', '2026-01-05', '2026-01-11'),
    ('2026-W03', '2026-01-12', '2026-01-18'),
    ('2026-W04', '2026-01-19', '2026-01-25'),
    ('2026-W05', '2026-01-26', '2026-02-01'),
    ('2026-W06', '2026-02-02', '2026-02-08'),
    ('2026-W07', '2026-02-09', '2026-02-15'),
]

def push_week(wk, events):
    formatted = [{'agent': e['a'], 'title': e['t'], 'start': e['s'], 'end': e['n'], 'description': e.get('d',''), 'location': e.get('l','')} for e in events]
    synced = 0
    for i in range(0, len(formatted), 25):
        chunk = formatted[i:i+25]
        for attempt in range(5):
            try:
                r = requests.post(f'{API}/api/sync', json={'week': wk, 'events': chunk, 'api_key': KEY}, timeout=120)
                if r.status_code == 200:
                    synced += len(chunk)
                    break
                print(f'  {wk} chunk@{i} attempt {attempt+1}: HTTP {r.status_code}', flush=True)
            except Exception as ex:
                print(f'  {wk} chunk@{i} attempt {attempt+1}: {ex}', flush=True)
            time.sleep(10 * (attempt + 1))
        time.sleep(3)
    return synced

# Read cached files and push
for wk, start, end in WEEKS:
    cache = f'events_cache/{wk}.json'
    if os.path.exists(cache) and os.path.getsize(cache) > 100:
        print(f'{wk}: reading cache...', flush=True)
        with open(cache) as f:
            data = json.load(f)
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict) and 'events' in data:
            events = data['events']
        else:
            events = data
        # Convert to compact if needed
        if events and 'agent' in events[0]:
            events = [{'a': e['agent'], 't': e['title'], 's': e['start'], 'n': e['end'], 'd': e.get('description','')[:100], 'l': e.get('location','')[:100]} for e in events]
        print(f'  {len(events)} events, pushing...', flush=True)
        synced = push_week(wk, events)
        print(f'  pushed {synced}/{len(events)}', flush=True)
    else:
        print(f'{wk}: NO CACHE - need browser fetch', flush=True)

# Classify all
print('\n=== CLASSIFYING ===', flush=True)
for wk, _, _ in WEEKS:
    try:
        s = requests.get(f'{API}/api/status?week={wk}', timeout=30).json()
        if s.get('unclassified', 0) > 0:
            print(f'{wk}: classifying {s["unclassified"]}...', flush=True)
            requests.post(f'{API}/api/classify', json={'week': wk}, headers={'X-API-Key': KEY}, timeout=30)
            for i in range(120):
                time.sleep(5)
                p = requests.get(f'{API}/api/classify/progress?week={wk}', timeout=30).json()
                if not p.get('running', False) and i > 2:
                    print(f'  {wk} done: {p.get("done",0)}', flush=True)
                    break
                if i % 12 == 0:
                    print(f'  {wk}: {p.get("done",0)}/{p.get("total",0)}', flush=True)
        else:
            print(f'{wk}: {s.get("total",0)} events, already classified', flush=True)
    except Exception as e:
        print(f'{wk}: {e}', flush=True)

# Final
print('\n=== FINAL ===', flush=True)
for w in range(1, 11):
    wk = f'2026-W{w:02d}'
    try:
        d = requests.get(f'{API}/api/status?week={wk}', timeout=30).json()
        print(f'{wk}: {d["total"]} events, {d["sales"]} sales', flush=True)
    except:
        pass
