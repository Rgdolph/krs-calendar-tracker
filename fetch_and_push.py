"""
Reads a compact JSON file and pushes events to the Render API.
Usage: python fetch_and_push.py <week> <json_file>
"""
import json, requests, time, sys

API_KEY = "krs-sync-2026-x7qm9p"
BASE_URL = "https://krs-calendar-tracker.onrender.com"

def push_week(week, filepath):
    with open(filepath) as f:
        compact = json.load(f)
    
    # Expand compact format
    events = []
    for e in compact:
        events.append({
            "agent": e.get("a", e.get("agent", "")),
            "title": e.get("t", e.get("title", "")),
            "start": e.get("s", e.get("start", "")),
            "end": e.get("n", e.get("end", "")),
            "description": e.get("d", e.get("description", "")),
            "location": e.get("l", e.get("location", ""))
        })
    
    print(f"{week}: {len(events)} events")
    
    for i in range(0, len(events), 25):
        chunk = events[i:i+25]
        try:
            r = requests.post(f"{BASE_URL}/api/sync", json={
                "week": week, "events": chunk, "api_key": API_KEY
            }, timeout=30)
            print(f"  Sync {i//25+1}: {r.status_code} {r.text[:80]}")
        except Exception as ex:
            print(f"  Sync {i//25+1} ERROR: {ex}")
        time.sleep(1)
    
    try:
        r = requests.post(f"{BASE_URL}/api/classify", json={"week": week},
                         headers={"X-API-Key": API_KEY}, timeout=120)
        print(f"  Classify: {r.status_code} {r.text[:150]}")
    except Exception as ex:
        print(f"  Classify ERROR: {ex}")

if __name__ == "__main__":
    week = sys.argv[1]
    filepath = sys.argv[2]
    push_week(week, filepath)
