"""Backfill weeks W01-W07 (Jan 1 - Feb 15, 2026) via Apps Script + cloud push."""
import json, requests, time
from datetime import date, timedelta

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'
APPS_SCRIPT = 'https://script.google.com/a/macros/krs.insure/s/AKfycbwN46cLo1aqtgwYz6CBAig_WOaBM2x1MTlYkcDbuXrejwAFfRfWgXazG_Qo3Yn0s2Ekzw/exec'

def week_dates(year, week):
    """Return (monday, sunday) for a given ISO week."""
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday

def fetch_from_apps_script(start_date, end_date):
    """Fetch events from Apps Script for a date range."""
    params = {
        'action': 'getEvents',
        'startDate': start_date.isoformat(),
        'endDate': end_date.isoformat()
    }
    print(f'  Fetching {start_date} to {end_date} from Apps Script...', flush=True)
    r = requests.get(APPS_SCRIPT, params=params, timeout=120)
    if r.status_code == 200:
        try:
            data = r.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'events' in data:
                return data['events']
            else:
                print(f'  Unexpected response format: {str(data)[:200]}', flush=True)
                return []
        except:
            print(f'  JSON parse error: {r.text[:200]}', flush=True)
            return []
    else:
        print(f'  HTTP {r.status_code}: {r.text[:200]}', flush=True)
        return []

def push_events(wk, events):
    """Push events to the cloud API."""
    synced = 0
    for i in range(0, len(events), 25):
        chunk = events[i:i+25]
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
    return synced

def classify_week(wk):
    """Trigger and wait for classification."""
    try:
        r = requests.post(f'{API}/api/classify', json={'week': wk}, headers={'X-API-Key': KEY}, timeout=30)
        print(f'  {wk} classify started: {r.text[:80]}', flush=True)
    except Exception as e:
        print(f'  {wk} classify trigger error: {e}', flush=True)
        return
    
    for i in range(120):
        time.sleep(5)
        try:
            p = requests.get(f'{API}/api/classify/progress?week={wk}', timeout=30).json()
            done = p.get('done', 0)
            total = p.get('total', 0)
            running = p.get('running', False)
            if i % 6 == 0:
                print(f'  {wk}: {done}/{total} running={running}', flush=True)
            if not running and i > 2:
                print(f'  {wk} classify DONE: {done}/{total}', flush=True)
                return
        except:
            pass
    print(f'  {wk} classify timed out', flush=True)

# Wake up the app first
print('Waking up app...', flush=True)
for i in range(30):
    try:
        r = requests.get(f'{API}/', timeout=120)
        if r.status_code == 200:
            print('App is live!', flush=True)
            break
    except:
        pass
    time.sleep(10)

# Process weeks W01 through W07
weeks = list(range(1, 8))  # W01 to W07

for w in weeks:
    wk = f'2026-W{w:02d}'
    monday, sunday = week_dates(2026, w)
    print(f'\n=== {wk} ({monday} to {sunday}) ===', flush=True)
    
    # Fetch from Apps Script
    raw_events = fetch_from_apps_script(monday, sunday)
    print(f'  Got {len(raw_events)} raw events', flush=True)
    
    if not raw_events:
        print(f'  Skipping (no events)', flush=True)
        continue
    
    # Convert to the format the API expects
    events = []
    for e in raw_events:
        events.append({
            'agent': e.get('agent', e.get('agent_name', '')),
            'title': e.get('title', e.get('summary', '')),
            'start': e.get('start', e.get('start_time', '')),
            'end': e.get('end', e.get('end_time', '')),
            'description': e.get('description', ''),
            'location': e.get('location', '')
        })
    
    # Push to cloud
    synced = push_events(wk, events)
    print(f'  {wk}: synced {synced}/{len(events)}', flush=True)
    
    # Save cache locally
    with open(f'events_cache/{wk}.json', 'w') as f:
        json.dump(raw_events, f, indent=2)
    
    time.sleep(5)

# Classify all weeks sequentially
print('\n=== CLASSIFYING ===', flush=True)
for w in weeks:
    wk = f'2026-W{w:02d}'
    # Check if there are events to classify
    try:
        status = requests.get(f'{API}/api/status?week={wk}', timeout=30).json()
        if status.get('unclassified', 0) > 0:
            print(f'\nClassifying {wk} ({status["unclassified"]} unclassified)...', flush=True)
            classify_week(wk)
        else:
            print(f'{wk}: already done or no events', flush=True)
    except:
        pass
    time.sleep(5)

# Final status
print('\n=== FINAL STATUS ===', flush=True)
for w in list(range(1, 11)):
    wk = f'2026-W{w:02d}'
    try:
        r = requests.get(f'{API}/api/status?week={wk}', timeout=30)
        d = r.json()
        print(f'{wk}: {d["total"]} events, {d["classified"]} classified, {d["sales"]} sales', flush=True)
    except:
        pass
