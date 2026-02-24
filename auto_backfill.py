"""
Auto-backfill: reads a JSON file with all events and pushes to Render API.
Usage: python auto_backfill.py <week> 
Reads from events_cache/<week>.json
"""
import json, sys, requests, time, os

API_KEY = "krs-sync-2026-x7qm9p"
BASE = "https://krs-calendar-tracker.onrender.com"

def push_week(week):
    fp = f"events_cache/{week}.json"
    with open(fp) as f:
        raw = json.load(f)
    events = raw.get("events", raw) if isinstance(raw, dict) else raw
    
    print(f"{week}: {len(events)} events from {fp}")
    
    for i in range(0, len(events), 25):
        chunk = events[i:i+25]
        fmt = [{k: e.get(k, "") for k in ["agent","title","start","end","description","location"]} for e in chunk]
        r = requests.post(f"{BASE}/api/sync", json={"week":week,"events":fmt,"api_key":API_KEY}, timeout=30)
        print(f"  chunk {i//25+1}: {r.status_code} {r.text[:60]}")
        time.sleep(0.5)
    
    print(f"  Classifying...")
    r = requests.post(f"{BASE}/api/classify", json={"week":week}, headers={"X-API-Key":API_KEY}, timeout=120)
    print(f"  classify: {r.status_code} {r.text[:100]}")

if __name__ == "__main__":
    for week in sys.argv[1:]:
        push_week(week)
        time.sleep(1)
