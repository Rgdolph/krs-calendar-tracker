import base64, json

b64 = open('w01_b64.txt').read().strip()
data = json.loads(base64.b64decode(b64).decode('utf-8'))
with open('events_cache/2026-W01.json', 'w') as f:
    json.dump(data, f)
print(f"Saved {len(data)} events to events_cache/2026-W01.json")
