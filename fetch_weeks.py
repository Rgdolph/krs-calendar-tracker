"""Fetch W04-W07 from Apps Script via Playwright CDP, save to cache."""
import json, asyncio

CDP_URL = 'http://127.0.0.1:18800'
SCRIPT = 'https://script.google.com/a/macros/krs.insure/s/AKfycbwN46cLo1aqtgwYz6CBAig_WOaBM2x1MTlYkcDbuXrejwAFfRfWgXazG_Qo3Yn0s2Ekzw/exec'

WEEKS = [
    ('2026-W04', '2026-01-19', '2026-01-25'),
    ('2026-W05', '2026-01-26', '2026-02-01'),
    ('2026-W06', '2026-02-02', '2026-02-08'),
    ('2026-W07', '2026-02-09', '2026-02-15'),
]

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()
        
        for wk, start, end in WEEKS:
            url = f'{SCRIPT}?start={start}&end={end}'
            print(f'{wk}: fetching...', flush=True)
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(10000)
            
            text = await page.evaluate('() => document.body.innerText')
            try:
                data = json.loads(text)
                events = data.get('events', data if isinstance(data, list) else [])
            except:
                print(f'  {wk}: JSON parse failed: {text[:200]}', flush=True)
                continue
            
            compact = [{'a':e.get('agent',''),'t':e.get('title',''),'s':e.get('start',''),'n':e.get('end',''),'d':(e.get('description','')or'')[:100],'l':(e.get('location','')or'')[:100]} for e in events]
            with open(f'events_cache/{wk}.json', 'w') as f:
                json.dump(compact, f)
            print(f'  {wk}: saved {len(compact)} events', flush=True)
        
        await page.close()
    print('Done fetching!', flush=True)

asyncio.run(main())
