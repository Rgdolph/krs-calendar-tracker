import json
import os
import subprocess
from openai import OpenAI
from database import get_learned_examples, update_classification, get_unclassified_events

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "classify_progress.json")

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {}
    config["openai_api_key"] = os.environ.get("OPENAI_API_KEY", config.get("openai_api_key", ""))
    return config

def get_progress():
    try:
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"running": False, "done": 0, "total": 0, "current": ""}

def _write_progress(data):
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, PROGRESS_FILE)

def build_system_prompt():
    examples = get_learned_examples()
    examples_text = ""
    if examples:
        examples_text = "\n\nThe manager has corrected these classifications — learn from them:\n"
        for ex in examples:
            examples_text += f'- "{ex["event_title"]}" should be {ex["corrected_classification"]}\n'

    return f"""You classify calendar events for insurance agents at Key Retirement Solutions.
They sell Medicare supplements, LTC insurance, life insurance, annuities, and retirement planning.

**sales** = a meeting with a client or prospect about insurance/financial products.
This includes: initial consultations, policy reviews, follow-ups with clients, Medicare reviews, annuity discussions, life insurance conversations, phone appointments with clients.
Events that contain what look like people's names (especially with product mentions) are almost always sales.

**not_sales** = anything that is NOT a client/prospect meeting.
This includes: internal team meetings, training sessions, personal events, church, sports, errands, travel time, admin blocks, prospecting/calling blocks (prospecting is outreach, not a confirmed appointment), social events, family events, generic blocked time, office time, door knocking.

If the title is ambiguous or empty, classify as not_sales.
{examples_text}
You will receive a JSON array of events. Classify ALL of them.
Respond with a JSON object: {{"results": [{{"id": "event_id", "classification": "sales" or "not_sales", "confidence": 0.0-1.0, "reasoning": "brief reason"}}]}}"""


def classify_batch_openai(events):
    """Classify a batch of events using GPT-4o-mini."""
    if not events:
        return []

    config = load_config()
    client = OpenAI(api_key=config["openai_api_key"])

    event_list = [{"id": e["id"], "title": e["title"], "agent": e["agent_name"]} for e in events]

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": json.dumps(event_list)}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        raw = json.loads(resp.choices[0].message.content)

        # Extract results list from response
        results = None
        if isinstance(raw, dict):
            for v in raw.values():
                if isinstance(v, list):
                    results = v
                    break
        elif isinstance(raw, list):
            results = raw

        if not results:
            print(f"[classify] Unexpected response: {list(raw.keys()) if isinstance(raw, dict) else type(raw)}", flush=True)
            return []

        # Update database
        classified = 0
        for r in results:
            if "id" in r and "classification" in r:
                cls = r["classification"].lower().strip()
                if cls in ("sales", "not_sales"):
                    update_classification(r["id"], cls, r.get("confidence", 0.5), r.get("reasoning", ""))
                    classified += 1

        print(f"[classify] Batch: sent {len(event_list)}, got {len(results)}, saved {classified}", flush=True)
        return results

    except Exception as e:
        print(f"[classify] OpenAI error: {e}", flush=True)
        return []


def _classify_thread(week_key, reclassify_all=False):
    """Background classification in a thread (no subprocess, no DB lock issues)."""
    import time
    try:
        if reclassify_all:
            from database import get_events_for_week
            events = get_events_for_week(week_key)
        else:
            events = get_unclassified_events(week_key)
        total = len(events)
        _write_progress({"running": True, "done": 0, "total": total, "current": "starting..."})
        
        batch_size = 20
        done = 0
        for i in range(0, total, batch_size):
            batch = events[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            _write_progress({"running": True, "done": done, "total": total, "current": f"Batch {batch_num}..."})
            classify_batch_openai(batch)
            done += len(batch)
            _write_progress({"running": True, "done": done, "total": total, "current": f"Batch {batch_num} done"})
            time.sleep(1)
        
        _write_progress({"running": False, "done": done, "total": total, "current": "complete"})
    except Exception as e:
        _write_progress({"running": False, "done": 0, "total": 0, "current": f"error: {e}"})

def classify_events_async(week_key, reclassify_all=False):
    """Start background classification in a thread."""
    import threading
    progress = get_progress()
    if progress.get("running"):
        return False

    _write_progress({"running": True, "done": 0, "total": 0, "current": "starting..."})
    t = threading.Thread(target=_classify_thread, args=(week_key, reclassify_all), daemon=True)
    t.start()
    return True


def classify_events(events):
    """Synchronous batch classification."""
    all_results = []
    batch_size = 20
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        results = classify_batch_openai(batch)
        all_results.extend(results)
    return all_results
