"""Classify events LOCALLY with GPT-4o-mini, then upload pre-classified to Render.
No git deploy step — endpoint already deployed."""
import json, os, sys, time, requests
from openai import OpenAI

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'

config_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(config_path) as f:
    config = json.load(f)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", config.get("openai_api_key", "")))

SYSTEM_PROMPT = """You classify calendar events for insurance agents at Key Retirement Solutions.
They sell Medicare supplements, LTC insurance, life insurance, annuities, and retirement planning.

**sales** = a meeting with a client or prospect about insurance/financial products.
This includes: initial consultations, policy reviews, follow-ups with clients, Medicare reviews, annuity discussions, life insurance conversations, phone appointments with clients.
Events that contain what look like people's names (especially with product mentions) are almost always sales.

**not_sales** = anything that is NOT a client/prospect meeting.
This includes: internal team meetings, training sessions, personal events, church, sports, errands, travel time, admin blocks, prospecting/calling blocks, social events, family events, generic blocked time, office time, door knocking.

If the title is ambiguous or empty, classify as not_sales.

Respond with a JSON object: {"results": [{"id": "event_id", "classification": "sales" or "not_sales", "confidence": 0.0-1.0, "reasoning": "brief reason"}]}"""

def classify_batch(events):
    batch = [{"id": i, "title": e.get("t", e.get("title","")), "agent": e.get("a", e.get("agent",""))} for i, e in enumerate(events)]
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(batch)}],
                temperature=0.1, response_format={"type": "json_object"},
                timeout=30)
            raw = json.loads(resp.choices[0].message.content)
            for v in (raw.values() if isinstance(raw, dict) else [raw]):
                if isinstance(v, list): return v
            return []
        except Exception as e:
            print(f'  GPT attempt {attempt+1}: {e}', flush=True)
            time.sleep(5 * (attempt + 1))
    return []

def process_week(wk):
    cache = f'events_cache/{wk}.json'
    if not os.path.exists(cache):
        print(f'{wk}: no cache file', flush=True)
        return
    with open(cache) as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = events.get('events', events)
    
    print(f'{wk}: {len(events)} events → classifying locally...', flush=True)
    classified = []
    for i in range(0, len(events), 20):
        batch = events[i:i+20]
        results = classify_batch(batch)
        rmap = {r["id"]: r for r in results}
        for j, ev in enumerate(batch):
            r = rmap.get(j, {})
            classified.append({
                "agent": ev.get("a", ev.get("agent", "")),
                "title": ev.get("t", ev.get("title", "")),
                "start": ev.get("s", ev.get("start", "")),
                "end": ev.get("n", ev.get("end", "")),
                "description": (ev.get("d", ev.get("description", "")) or "")[:100],
                "location": (ev.get("l", ev.get("location", "")) or "")[:100],
                "classification": r.get("classification", "not_sales"),
                "confidence": r.get("confidence", 0.5),
                "reasoning": r.get("reasoning", "")
            })
        print(f'  classified {min(i+20, len(events))}/{len(events)}', flush=True)
        time.sleep(0.3)
    
    sales = sum(1 for e in classified if e["classification"] == "sales")
    print(f'{wk}: {sales} sales / {len(classified)} total → uploading...', flush=True)
    
    uploaded = 0
    for i in range(0, len(classified), 25):
        chunk = classified[i:i+25]
        for attempt in range(5):
            try:
                r = requests.post(f'{API}/api/sync-classified',
                    json={'week': wk, 'events': chunk, 'api_key': KEY}, timeout=180)
                if r.status_code == 200:
                    uploaded += len(chunk)
                    break
                print(f'  chunk {i//25+1}: HTTP {r.status_code}', flush=True)
            except Exception as ex:
                print(f'  chunk {i//25+1}: {ex}', flush=True)
            time.sleep(10 * (attempt + 1))
        time.sleep(1)
    print(f'{wk}: ✓ uploaded {uploaded}', flush=True)

# Wake Render
print('Waking Render...', flush=True)
for i in range(15):
    try:
        if requests.get(f'{API}/', timeout=120).status_code == 200:
            print('Ready!\n', flush=True)
            break
    except: pass
    time.sleep(10)

weeks = sys.argv[1:] if len(sys.argv) > 1 else [f'2026-W{i:02d}' for i in range(1, 8)]
for wk in weeks:
    process_week(wk)
    time.sleep(1)

print('\n=== FINAL ===', flush=True)
for w in range(1, 11):
    wk = f'2026-W{w:02d}'
    try:
        d = requests.get(f'{API}/api/status?week={wk}', timeout=120).json()
        print(f'{wk}: {d["total"]} events, {d["sales"]} sales, {d.get("unclassified",0)} unclassified', flush=True)
    except: pass
