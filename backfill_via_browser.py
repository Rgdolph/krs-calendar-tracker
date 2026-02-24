"""Backfill W01-W07 by fetching from Apps Script doGet (via direct URL) and pushing to Render.
The Apps Script doGet accepts ?start=YYYY-MM-DD&end=YYYY-MM-DD and returns JSON."""
import json, requests, time, sys
from datetime import date, timedelta

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'
SCRIPT_URL = 'https://script.google.com/a/macros/krs.insure/s/AKfycbwN46cLo1aqtgwYz6CBAig_WOaBM2x1MTlYkcDbuXrejwAFfRfWgXazG_Qo3Yn0s2Ekzw/exec'

def week_dates(year, week):
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday

def fetch_week(year, week):
    monday, sunday = week_dates(year, week)
    wk = f'{year}-W{week:02d}'
    print(f'Fetching {wk} ({monday} to {sunday})...', flush=True)
    try:
        r = requests.get(SCRIPT_URL, params={'start': monday.isoformat(), 'end': sunday.isoformat()}, timeout=120, allow_redirects=True)
        if r.status_code == 200:
            data = r.json()
            events = data.get('events', data if isinstance(data, list) else [])
            print(f'  Got {len(events)} events', flush=True)
            return wk, events
        else:
            print(f'  HTTP {r.status_code}', flush=True)
            return wk, []
    except Exception as e:
        print(f'  Error: {e}', flush=True)
        return wk, []

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

# Wake app
print('Waking app...', flush=True)
for i in range(10):
    try:
        r = requests.get(f'{API}/', timeout=120)
        if r.status_code == 200:
            print('App ready!', flush=True)
            break
    except:
        pass
    time.sleep(10)

# Fetch and push W01-W07
for w in range(1, 8):
    wk, events = fetch_week(2026, w)
    if events:
        push_events(wk, events)
    time.sleep(2)

# Trigger classification for all new weeks
print('\nTriggering classification...', flush=True)
for w in range(1, 8):
    wk = f'2026-W{w:02d}'
    try:
        status = requests.get(f'{API}/api/status?week={wk}', timeout=30).json()
        if status.get('unclassified', 0) > 0:
            print(f'Classifying {wk} ({status["unclassified"]} unclassified)...', flush=True)
            requests.post(f'{API}/api/classify', json={'week': wk}, headers={'X-API-Key': KEY}, timeout=30)
            # Wait for it to finish
            for i in range(120):
                time.sleep(5)
                try:
                    p = requests.get(f'{API}/api/classify/progress?week={wk}', timeout=30).json()
                    if not p.get('running', False) and i > 2:
                        print(f'  {wk} done: {p.get("done",0)} classified', flush=True)
                        break
                except:
                    pass
        else:
            print(f'{wk}: no events or already classified', flush=True)
    except Exception as e:
        print(f'{wk} error: {e}', flush=True)
    time.sleep(3)

# Final
print('\n=== FINAL STATUS (W01-W10) ===', flush=True)
for w in range(1, 11):
    wk = f'2026-W{w:02d}'
    try:
        d = requests.get(f'{API}/api/status?week={wk}', timeout=30).json()
        print(f'{wk}: {d["total"]} events, {d["classified"]} classified, {d["sales"]} sales', flush=True)
    except:
        pass
