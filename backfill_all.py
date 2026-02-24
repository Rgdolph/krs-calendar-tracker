"""
Backfill script: reads events_cache/2026-WXX.json files and pushes them to Render API.
Run after all JSON files are saved from browser.
"""
import json, requests, time, os, glob

API_KEY = "krs-sync-2026-x7qm9p"
BASE_URL = "https://krs-calendar-tracker.onrender.com"

def push_week(week, events):
    print(f"\n=== {week}: {len(events)} events ===")
    compact = []
    for e in events:
        compact.append({
            "agent": e.get("agent", e.get("a", "")),
            "title": e.get("title", e.get("t", "")),
            "start": e.get("start", e.get("s", "")),
            "end": e.get("end", e.get("n", "")),
            "description": e.get("description", e.get("d", "")),
            "location": e.get("location", e.get("l", ""))
        })
    
    for i in range(0, len(compact), 25):
        chunk = compact[i:i+25]
        try:
            r = requests.post(f"{BASE_URL}/api/sync", json={
                "week": week, "events": chunk, "api_key": API_KEY
            }, timeout=30)
            print(f"  Sync chunk {i//25+1}: {r.status_code} - {r.text[:100]}")
        except Exception as ex:
            print(f"  Sync chunk {i//25+1} ERROR: {ex}")
        time.sleep(1)
    
    try:
        r = requests.post(f"{BASE_URL}/api/classify", json={"week": week},
                         headers={"X-API-Key": API_KEY}, timeout=120)
        print(f"  Classify: {r.status_code} - {r.text[:200]}")
    except Exception as ex:
        print(f"  Classify ERROR: {ex}")

# Process all cached week files
weeks = ["2026-W01","2026-W02","2026-W03","2026-W04","2026-W05","2026-W06","2026-W07"]
for week in weeks:
    filepath = f"events_cache/{week}.json"
    if not os.path.exists(filepath):
        print(f"SKIP {week}: no file")
        continue
    with open(filepath) as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("events", [])
    if len(data) < 2:
        print(f"SKIP {week}: only {len(data)} events (likely placeholder)")
        continue
    push_week(week, data)
    time.sleep(2)

print("\n=== Checking status for W01-W10 ===")
for w in range(1, 11):
    week = f"2026-W{w:02d}"
    try:
        r = requests.get(f"{BASE_URL}/api/week/{week}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            print(f"  {week}: {d.get('event_count', '?')} events, classified={d.get('classified', '?')}")
        else:
            print(f"  {week}: {r.status_code}")
    except Exception as ex:
        print(f"  {week}: ERROR {ex}")
