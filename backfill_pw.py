"""Backfill W01-W07 using Playwright to connect to the OpenClaw browser."""
import json, requests, time, asyncio, os, sys

API = 'https://krs-calendar-tracker.onrender.com'
KEY = 'krs-sync-2026-x7qm9p'
SCRIPT = 'https://script.google.com/a/macros/krs.insure/s/AKfycbwN46cLo1aqtgwYz6CBAig_WOaBM2x1MTlYkcDbuXrejwAFfRfWgXazG_Qo3Yn0s2Ekzw/exec'
CDP_URL = 'http://127.0.0.1:18800'

WEEKS = [
    ('2026-W01', '2025-12-29', '2026-01-04'),
    ('2026-W02', '2026-01-05', '2026-01-11'),
    ('2026-W03', '2026-01-12', '2026-01-18'),
    ('2026-W04', '2026-01-19', '2026-01-25'),
    ('2026-W05', '2026-01-26', '2026-02-01'),
    ('2026-W06', '2026-02-02', '2026-02-08'),
    ('2026-W07', '2026-02-09', '2026-02-15'),
]

def push_week(wk, events):
    formatted = [{'agent': e.get('a',e.get('agent','')), 'title': e.get('t',e.get('title','')), 'start': e.get('s',e.get('start','')), 'end': e.get('n',e.get('end','')), 'description': e.get('d',e.get('description',''))[:100], 'location': e.get('l',e.get('location',''))[:100]} for e in events]
    synced = 0
    for i in range(0, len(formatted), 25):
        chunk = formatted[i:i+25]
        for attempt in range(5):
            try:
                r = requests.post(f'{API}/api/sync', json={'week': wk, 'events': chunk, 'api_key': KEY}, timeout=120)
                if r.status_code == 200:
                    synced += len(chunk)
                    break
                print(f'  {wk} chunk@{i} attempt {attempt+1}: HTTP {r.status_code}', flush=True)
            except Exception as ex:
                print(f'  {wk} chunk@{i} attempt {attempt+1}: {ex}', flush=True)
            time.sleep(10 * (attempt + 1))
        time.sleep(3)
    return synced

async def fetch_and_push():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        
        for wk, start, end in WEEKS:
            cache = f'events_cache/{wk}.json'
            if os.path.exists(cache) and os.path.getsize(cache) > 1000:
                print(f'{wk}: using cache', flush=True)
                with open(cache) as f:
                    events = json.load(f)
                    if isinstance(events, dict):
                        events = events.get('events', [])
            else:
                url = f'{SCRIPT}?start={start}&end={end}'
                print(f'{wk}: fetching from Apps Script...', flush=True)
                await page.goto(url, wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(5000)
                
                text = await page.evaluate('() => document.body.innerText')
                try:
                    data = json.loads(text)
                    events = data.get('events', data if isinstance(data, list) else [])
                except:
                    print(f'  {wk}: JSON parse failed, text={text[:100]}', flush=True)
                    continue
                
                # Save compact
                compact = [{'a': e.get('agent',''), 't': e.get('title',''), 's': e.get('start',''), 'n': e.get('end',''), 'd': (e.get('description','') or '')[:100], 'l': (e.get('location','') or '')[:100]} for e in events]
                with open(cache, 'w') as f:
                    json.dump(compact, f)
                events = compact
            
            print(f'  {wk}: {len(events)} events, pushing...', flush=True)
            synced = push_week(wk, events)
            print(f'  {wk}: pushed {synced}/{len(events)}', flush=True)
            time.sleep(5)
        
        await page.close()
    
    # Classify all
    print('\n=== CLASSIFYING ===', flush=True)
    for wk, _, _ in WEEKS:
        try:
            s = requests.get(f'{API}/api/status?week={wk}', timeout=60).json()
            if s.get('unclassified', 0) > 0:
                print(f'{wk}: classifying {s["unclassified"]}...', flush=True)
                requests.post(f'{API}/api/classify', json={'week': wk}, headers={'X-API-Key': KEY}, timeout=30)
                for i in range(180):
                    time.sleep(5)
                    p = requests.get(f'{API}/api/classify/progress?week={wk}', timeout=30).json()
                    if not p.get('running', False) and i > 2:
                        print(f'  {wk} done: {p.get("done",0)}', flush=True)
                        break
                    if i % 12 == 0:
                        print(f'  {wk}: {p.get("done",0)}/{p.get("total",0)}', flush=True)
            else:
                print(f'{wk}: {s.get("total",0)} events, already done', flush=True)
        except Exception as e:
            print(f'{wk}: {e}', flush=True)
        time.sleep(3)
    
    # Final
    print('\n=== FINAL STATUS ===', flush=True)
    for w in range(1, 11):
        wk = f'2026-W{w:02d}'
        try:
            d = requests.get(f'{API}/api/status?week={wk}', timeout=30).json()
            print(f'{wk}: {d["total"]} events, {d["sales"]} sales', flush=True)
        except:
            pass

# Wake app first
print('Waking app...', flush=True)
for i in range(10):
    try:
        if requests.get(f'{API}/', timeout=120).status_code == 200:
            print('App ready!', flush=True)
            break
    except: pass
    time.sleep(10)

asyncio.run(fetch_and_push())
