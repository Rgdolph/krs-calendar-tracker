"""Classify locally with LARGE batches (100 per API call) then upload."""
import json, os, sys, time, requests
from openai import OpenAI

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'
BATCH_SIZE = 100  # Much bigger batches = fewer API calls

with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    config = json.load(f)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", config.get("openai_api_key", "")))

SYSTEM_PROMPT = """You classify calendar events for insurance agents at Key Retirement Solutions (Medicare, LTC, life, annuities, retirement).

sales = client/prospect meeting about insurance/financial products (consultations, reviews, follow-ups, Medicare reviews, phone appointments with clients, events with people's names + product context)

not_sales = everything else (team meetings, training, personal, errands, travel, admin, prospecting blocks, office time, door knocking, social, family)

Ambiguous or empty title = not_sales.

Return JSON: {"results": [{"id": <int>, "c": "s" or "n", "r": "brief reason"}]}
Use "s" for sales, "n" for not_sales. Keep reasoning under 10 words."""

def classify_batch(events):
    batch = [{"id": i, "t": e.get("t", e.get("title","")), "a": e.get("a", e.get("agent",""))} for i, e in enumerate(events)]
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(batch)}],
                temperature=0.1, response_format={"type": "json_object"},
                timeout=60)
            raw = json.loads(resp.choices[0].message.content)
            for v in (raw.values() if isinstance(raw, dict) else [raw]):
                if isinstance(v, list): return v
            return []
        except Exception as e:
            print(f'  GPT error attempt {attempt+1}: {e}', flush=True)
            time.sleep(10 * (attempt + 1))
    return []

def process_week(wk):
    cache = f'events_cache/{wk}.json'
    if not os.path.exists(cache):
        print(f'{wk}: no cache', flush=True)
        return
    with open(cache) as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = events.get('events', events)
    
    print(f'{wk}: {len(events)} events, classifying (batch={BATCH_SIZE})...', flush=True)
    classified = []
    for i in range(0, len(events), BATCH_SIZE):
        batch = events[i:i+BATCH_SIZE]
        t0 = time.time()
        results = classify_batch(batch)
        rmap = {r["id"]: r for r in results}
        for j, ev in enumerate(batch):
            r = rmap.get(j, {})
            c = r.get("c", r.get("classification", "n"))
            cls = "sales" if c in ("s", "sales") else "not_sales"
            classified.append({
                "agent": ev.get("a", ev.get("agent", "")),
                "title": ev.get("t", ev.get("title", "")),
                "start": ev.get("s", ev.get("start", "")),
                "end": ev.get("n", ev.get("end", "")),
                "description": (ev.get("d", ev.get("description", "")) or "")[:100],
                "location": (ev.get("l", ev.get("location", "")) or "")[:100],
                "classification": cls,
                "confidence": r.get("confidence", 0.8),
                "reasoning": r.get("r", r.get("reasoning", ""))
            })
        done = min(i + BATCH_SIZE, len(events))
        elapsed = time.time() - t0
        print(f'  {done}/{len(events)} ({elapsed:.1f}s)', flush=True)
        time.sleep(1)
    
    sales = sum(1 for e in classified if e["classification"] == "sales")
    print(f'{wk}: {sales} sales, uploading...', flush=True)
    
    uploaded = 0
    for i in range(0, len(classified), 50):
        chunk = classified[i:i+50]
        for attempt in range(5):
            try:
                r = requests.post(f'{API}/api/sync',
                    json={'week': wk, 'events': chunk, 'api_key': KEY}, timeout=180)
                if r.status_code == 200:
                    uploaded += len(chunk)
                    break
            except Exception as ex:
                print(f'  upload err: {ex}', flush=True)
            time.sleep(10 * (attempt + 1))
        time.sleep(1)
    print(f'{wk}: done ({uploaded} uploaded)', flush=True)

# Wake
print('Waking Render...', flush=True)
for i in range(15):
    try:
        if requests.get(f'{API}/', timeout=120).status_code == 200:
            print('Ready!', flush=True)
            break
    except: pass
    time.sleep(10)

weeks = sys.argv[1:] if len(sys.argv) > 1 else [f'2026-W{i:02d}' for i in range(4, 8)]
for wk in weeks:
    process_week(wk)
    time.sleep(2)

print('\n=== FINAL ===', flush=True)
for w in range(1, 11):
    wk = f'2026-W{w:02d}'
    try:
        d = requests.get(f'{API}/api/status?week={wk}', timeout=120).json()
        print(f'{wk}: {d["total"]} events, {d["sales"]} sales, {d.get("unclassified",0)} unc', flush=True)
    except: pass
