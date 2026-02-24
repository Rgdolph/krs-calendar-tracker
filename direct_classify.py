"""Classify unclassified events directly in PostgreSQL. No Render web app needed."""
import json, os, sys, time
import psycopg2
from openai import OpenAI

DB_URL = 'postgresql://krs_calendar_db_user:87GA8KEjZYd6vVIiSs9aqokIpInYgwDn@dpg-d6eg6b0gjchc73fcun70-a.oregon-postgres.render.com/krs_calendar_db'

with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    config = json.load(f)
import httpx
client = OpenAI(
    api_key=config.get('openai_api_key', ''),
    http_client=httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
)

SYSTEM_PROMPT = """You classify calendar events for insurance agents at Key Retirement Solutions (Medicare, LTC, life, annuities, retirement).

sales = client/prospect meeting about insurance/financial products (consultations, reviews, follow-ups, Medicare reviews, phone appointments with clients, events with people's names + product context)

not_sales = everything else (team meetings, training, personal, errands, travel, admin, prospecting blocks, office time, door knocking, social, family)

Ambiguous or empty title = not_sales.

Return JSON: {"results": [{"id": <int>, "c": "s" or "n", "r": "brief reason"}]}
Use "s" for sales, "n" for not_sales. Keep reasoning under 10 words."""

BATCH = 100

def classify_batch(events):
    batch = [{"id": e['idx'], "t": e['title'], "a": e['agent_name']} for e in events]
    for attempt in range(3):
        try:
            t0 = time.time()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(batch)}],
                temperature=0.1, response_format={"type": "json_object"},
                timeout=60)
            raw = json.loads(resp.choices[0].message.content)
            for v in (raw.values() if isinstance(raw, dict) else [raw]):
                if isinstance(v, list):
                    elapsed = time.time() - t0
                    return v, elapsed
            return [], time.time() - t0
        except Exception as e:
            print(f'  GPT error attempt {attempt+1}: {e}', flush=True)
            time.sleep(5 * (attempt + 1))
    return [], 0

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Get unclassified events
    weeks = sys.argv[1:] if len(sys.argv) > 1 else None
    if weeks:
        placeholders = ','.join(['%s'] * len(weeks))
        cur.execute(f"SELECT id, agent_name, title, week_key FROM events WHERE classification IS NULL AND week_key IN ({placeholders}) ORDER BY week_key, agent_name", weeks)
    else:
        cur.execute("SELECT id, agent_name, title, week_key FROM events WHERE classification IS NULL ORDER BY week_key, agent_name")
    
    rows = cur.fetchall()
    events = [{'id': r[0], 'agent_name': r[1], 'title': r[2], 'week_key': r[3]} for r in rows]
    
    if not events:
        print('Nothing to classify!', flush=True)
        # Show stats
        cur.execute("SELECT week_key, COUNT(*), SUM(CASE WHEN classification='sales' THEN 1 ELSE 0 END) as sales FROM events GROUP BY week_key ORDER BY week_key")
        for r in cur.fetchall():
            print(f'  {r[0]}: {r[1]} events, {r[2]} sales', flush=True)
        conn.close()
        return
    
    total = len(events)
    print(f'{total} unclassified events to process', flush=True)
    
    done = 0
    total_sales = 0
    for i in range(0, total, BATCH):
        batch = events[i:i+BATCH]
        for j, e in enumerate(batch):
            e['idx'] = j
        
        results, elapsed = classify_batch(batch)
        rmap = {r['id']: r for r in results}
        
        sales_in_batch = 0
        for j, e in enumerate(batch):
            r = rmap.get(j, {})
            c = r.get('c', r.get('classification', 'n'))
            cls = 'sales' if c in ('s', 'sales') else 'not_sales'
            reasoning = r.get('r', r.get('reasoning', ''))
            confidence = r.get('confidence', 0.8)
            if cls == 'sales':
                sales_in_batch += 1
            cur.execute("UPDATE events SET classification=%s, confidence=%s, ai_reasoning=%s WHERE id=%s",
                (cls, confidence, reasoning, e['id']))
        
        conn.commit()
        done += len(batch)
        total_sales += sales_in_batch
        print(f'  {done}/{total} classified ({sales_in_batch} sales in batch, {elapsed:.1f}s)', flush=True)
        time.sleep(0.5)
    
    print(f'\nDone! {total} events classified, {total_sales} total sales', flush=True)
    
    # Final stats
    print('\n=== ALL WEEKS ===', flush=True)
    cur.execute("SELECT week_key, COUNT(*), SUM(CASE WHEN classification='sales' THEN 1 ELSE 0 END) as sales, SUM(CASE WHEN classification IS NULL THEN 1 ELSE 0 END) as unc FROM events GROUP BY week_key ORDER BY week_key")
    for r in cur.fetchall():
        print(f'  {r[0]}: {r[1]} events, {r[2]} sales, {r[3]} unclassified', flush=True)
    
    conn.close()

if __name__ == '__main__':
    main()
