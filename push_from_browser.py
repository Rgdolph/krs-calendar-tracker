"""
Push events directly using Python requests.
Reads JSON from events_cache files and pushes to Render API.
Usage: python push_from_browser.py <week> <json_file>
Or: python push_from_browser.py --push-all (pushes all cached files)
"""
import json, requests, time, sys, os

API_KEY = "krs-sync-2026-x7qm9p"
BASE = "https://krs-calendar-tracker.onrender.com"

def push_and_classify(week, events):
    print(f"\n{week}: {len(events)} events")
    for i in range(0, len(events), 25):
        chunk = events[i:i+25]
        fmt = [{"agent":e.get("agent",""),"title":e.get("title",""),"start":e.get("start",""),
                "end":e.get("end",""),"description":e.get("description",""),"location":e.get("location","")} for e in chunk]
        r = requests.post(f"{BASE}/api/sync", json={"week":week,"events":fmt,"api_key":API_KEY}, timeout=30)
        print(f"  sync {i//25+1}: {r.status_code}")
        time.sleep(0.5)
    r = requests.post(f"{BASE}/api/classify", json={"week":week}, headers={"X-API-Key":API_KEY}, timeout=120)
    print(f"  classify: {r.status_code} {r.text[:100]}")

if "--push-all" in sys.argv:
    for w in range(1,8):
        wk = f"2026-W{w:02d}"
        fp = f"events_cache/{wk}.json"
        if not os.path.exists(fp):
            print(f"SKIP {wk}: no file")
            continue
        with open(fp) as f:
            data = json.load(f)
        events = data.get("events", data) if isinstance(data, dict) else data
        if len(events) < 2:
            print(f"SKIP {wk}: only {len(events)} events")
            continue
        push_and_classify(wk, events)
        time.sleep(1)
elif len(sys.argv) >= 3:
    week, fp = sys.argv[1], sys.argv[2]
    with open(fp) as f:
        data = json.load(f)
    events = data.get("events", data) if isinstance(data, dict) else data
    push_and_classify(week, events)

# Final status
print("\n=== Status W01-W10 ===")
for w in range(1,11):
    wk = f"2026-W{w:02d}"
    r = requests.get(f"{BASE}/api/status?week={wk}", timeout=10)
    print(f"  {wk}: {r.text[:80]}")
