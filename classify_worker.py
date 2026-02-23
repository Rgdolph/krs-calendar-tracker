"""Background worker: classifies all unclassified events for a week using GPT-4o-mini."""
import sys
import json
import os
import traceback

sys.path.insert(0, os.path.dirname(__file__))

import database as db
import classifier

PROGRESS_FILE = classifier.PROGRESS_FILE

def write_progress(data):
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, PROGRESS_FILE)

def main():
    week_key = sys.argv[1] if len(sys.argv) > 1 else None
    if not week_key:
        print("Usage: python classify_worker.py <week_key>", flush=True)
        sys.exit(1)

    try:
        events = db.get_unclassified_events(week_key)
        total = len(events)
        print(f"[worker] Classifying {total} events for {week_key} via GPT-4o-mini", flush=True)
        write_progress({"running": True, "done": 0, "total": total, "current": "starting..."})

        batch_size = 20
        done = 0
        for i in range(0, total, batch_size):
            batch = events[i:i+batch_size]
            batch_num = i // batch_size + 1
            write_progress({"running": True, "done": done, "total": total, "current": f"Batch {batch_num}..."})

            try:
                print(f"[worker] Starting batch {batch_num} ({len(batch)} events)...", flush=True)
                results = classifier.classify_batch_openai(batch)
                classified = len([r for r in results if "id" in r and "classification" in r])
                done += classified
                print(f"[worker] Batch {batch_num}: {len(batch)} sent, {classified} classified", flush=True)
            except Exception as batch_ex:
                print(f"[worker] Batch {batch_num} ERROR: {batch_ex}", flush=True)
                import traceback
                traceback.print_exc(file=sys.stdout)
                sys.stdout.flush()

        write_progress({"running": False, "done": done, "total": total, "current": ""})
        print(f"[worker] Complete: {done}/{total} events classified", flush=True)

    except Exception as ex:
        print(f"[worker] Fatal error: {ex}", flush=True)
        traceback.print_exc()
        write_progress({"running": False, "done": 0, "total": 0, "current": f"Error: {str(ex)[:100]}"})

if __name__ == "__main__":
    main()
