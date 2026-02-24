"""
Complete backfill script. 
For each week, reads events_cache/2026-WXX.json, pushes to Render, classifies.
"""
import json, requests, time, os, sys

API_KEY = "krs-sync-2026-x7qm9p"
BASE_URL = "https://krs-calendar-tracker.onrender.com"

def push_week(week, events):
    print(f"\n=== {week}: {len(events)} events ===")
    
    # Push in chunks of 25
    for i in range(0, len(events), 25):
        chunk = events[i:i+25]
        # Convert to expected format
        formatted = []
        for e in chunk:
            formatted.append({
                "agent": e.get("agent", ""),
                "title": e.get("title", ""),
                "start": e.get("start", ""),
                "end": e.get("end", ""),
                "description": e.get("description", ""),
                "location": e.get("location", "")
            })
        try:
            r = requests.post(f"{BASE_URL}/api/sync", json={
                "week": week, "events": formatted, "api_key": API_KEY
            }, timeout=30)
            print(f"  Sync {i//25+1}/{(len(events)-1)//25+1}: {r.status_code} {r.text[:100]}")
        except Exception as ex:
            print(f"  Sync {i//25+1} ERROR: {ex}")
        time.sleep(1)
    
    # Classify
    try:
        r = requests.post(f"{BASE_URL}/api/classify", json={"week": week},
                         headers={"X-API-Key": API_KEY}, timeout=120)
        print(f"  Classify: {r.status_code} {r.text[:200]}")
    except Exception as ex:
        print(f"  Classify ERROR: {ex}")

# Process specified weeks or all
weeks_to_process = sys.argv[1:] if len(sys.argv) > 1 else [f"2026-W{i:02d}" for i in range(1,8)]

for week in weeks_to_process:
    filepath = f"events_cache/{week}.json"
    if not os.path.exists(filepath):
        print(f"SKIP {week}: no file at {filepath}")
        continue
    with open(filepath) as f:
        raw = json.load(f)
    
    # Handle both {events: [...]} and [...] formats
    events = raw.get("events", raw) if isinstance(raw, dict) else raw
    if not events or len(events) < 2:
        print(f"SKIP {week}: only {len(events) if events else 0} events")
        continue
    
    push_week(week, events)
    time.sleep(2)

# Status check
print("\n\n=== Final Status W01-W10 ===")
for w in range(1, 11):
    week = f"2026-W{w:02d}"
    try:
        r = requests.get(f"{BASE_URL}/api/week/{week}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            ec = d.get('event_count', d.get('events', '?'))
            cl = d.get('classified', d.get('classification', '?'))
            print(f"  {week}: events={ec}, classified={cl}")
        else:
            print(f"  {week}: HTTP {r.status_code} - {r.text[:80]}")
    except Exception as ex:
        print(f"  {week}: ERROR {ex}")
