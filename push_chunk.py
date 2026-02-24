"""Push a JSON chunk to the Render API. Reads JSON from stdin."""
import json, sys, requests

week = sys.argv[1]
events = json.loads(sys.stdin.read())
r = requests.post('https://krs-calendar-tracker.onrender.com/api/sync',
    json={'week': week, 'events': events, 'api_key': 'krs-sync-2026-x7qm9p'}, timeout=30)
print(f"{r.status_code}: {r.text[:100]}")
