import json, requests, sys, time

API_KEY = "krs-sync-2026-x7qm9p"
BASE_URL = "https://krs-calendar-tracker.onrender.com"

def push_week(week, events):
    """Push events in chunks of 25, then classify."""
    print(f"\n=== {week}: {len(events)} events ===")
    
    # Convert events to compact format (keep only needed fields)
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
    
    # Push in chunks of 25
    for i in range(0, len(compact), 25):
        chunk = compact[i:i+25]
        r = requests.post(f"{BASE_URL}/api/sync", json={
            "week": week,
            "events": chunk,
            "api_key": API_KEY
        }, timeout=30)
        print(f"  Chunk {i//25+1}: {r.status_code} - {r.text[:100]}")
        time.sleep(1)
    
    # Classify
    r = requests.post(f"{BASE_URL}/api/classify", json={"week": week},
                     headers={"X-API-Key": API_KEY}, timeout=60)
    print(f"  Classify: {r.status_code} - {r.text[:200]}")

def save_and_push(week, json_str):
    """Save JSON string to file and push."""
    data = json.loads(json_str)
    events = data.get("events", data) if isinstance(data, dict) else data
    
    # Save to file
    filepath = f"events_cache/{week}.json"
    with open(filepath, "w") as f:
        json.dump(events, f)
    print(f"Saved {len(events)} events to {filepath}")
    
    push_week(week, events)

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        week = sys.argv[1]
        json_file = sys.argv[2]
        with open(json_file) as f:
            events = json.load(f)
        if isinstance(events, dict):
            events = events.get("events", events)
        push_week(week, events)
