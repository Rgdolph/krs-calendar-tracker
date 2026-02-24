from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime, date, timedelta
import os
import database as db
import classifier
import calendar_source

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

import json

# Load config: env vars override config.json
_config_path = os.path.join(os.path.dirname(__file__), "config.json")
if os.path.exists(_config_path):
    with open(_config_path) as _f:
        APP_CONFIG = json.load(_f)
else:
    APP_CONFIG = {"agents": []}

# Env var overrides
APP_CONFIG["openai_api_key"] = os.environ.get("OPENAI_API_KEY", APP_CONFIG.get("openai_api_key", ""))
APP_CONFIG["apps_script_url"] = os.environ.get("APPS_SCRIPT_URL", APP_CONFIG.get("apps_script_url", ""))
APP_CONFIG["sync_api_key"] = os.environ.get("SYNC_API_KEY", APP_CONFIG.get("sync_api_key", ""))
APP_CONFIG["data_source"] = os.environ.get("DATA_SOURCE", APP_CONFIG.get("data_source", "script"))

def current_week_key():
    today = date.today()
    return today.strftime("%G-W%V")

def week_offset(week_key, offset):
    year, week = int(week_key[:4]), int(week_key.split('W')[1])
    d = date.fromisocalendar(year, week, 1) + timedelta(weeks=offset)
    return d.strftime("%G-W%V")

def week_display(week_key):
    year, week = int(week_key[:4]), int(week_key.split('W')[1])
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d, %Y')}"

@app.route("/")
def dashboard():
    wk = request.args.get("week", current_week_key())
    stats = db.get_agent_stats(wk)
    progress = classifier.get_progress()
    return render_template("dashboard.html",
        stats=stats, week=wk, week_display=week_display(wk),
        prev_week=week_offset(wk, -1), next_week=week_offset(wk, 1),
        current_week=current_week_key(), progress=progress, config=APP_CONFIG)

@app.route("/agent/<name>")
def agent_detail(name):
    wk = request.args.get("week", current_week_key())
    events = db.get_events_for_week(wk, name)
    return render_template("agent.html",
        events=events, agent_name=name, week=wk, week_display=week_display(wk),
        prev_week=week_offset(wk, -1), next_week=week_offset(wk, 1),
        current_week=current_week_key(), config=APP_CONFIG)

@app.route("/week/<week_key>/events")
def week_events(week_key):
    filt = request.args.get("filter", "sales")
    all_events = db.get_events_for_week(week_key)
    
    sales = [e for e in all_events if (e.get("override") or e.get("classification")) == "sales"]
    other = [e for e in all_events if (e.get("override") or e.get("classification")) != "sales"]
    
    if filt == "sales":
        events = sorted(sales, key=lambda e: (e.get("agent_name", ""), e.get("start_time", "")))
    elif filt == "other":
        events = sorted(other, key=lambda e: (e.get("agent_name", ""), e.get("start_time", "")))
    else:
        events = sorted(all_events, key=lambda e: (e.get("agent_name", ""), e.get("start_time", "")))
    
    return render_template("week_events.html",
        events=events, week=week_key, week_display=week_display(week_key),
        filter=filt, sales_count=len(sales), other_count=len(other), config=APP_CONFIG)

def check_api_key():
    """Verify sync API key if configured."""
    key = APP_CONFIG.get("sync_api_key", "")
    if not key:
        return True  # No key configured, allow (local dev)
    provided = request.headers.get("X-API-Key", "") or (request.get_json(force=True, silent=True) or {}).get("api_key", "") or request.args.get("api_key", "")
    return provided == key

@app.route("/api/sync", methods=["POST"])
def sync():
    if not check_api_key():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    wk = data.get("week", current_week_key())
    
    # If browser sent events directly (client-side fetch from Apps Script)
    raw_events = data.get("events", None)
    if raw_events:
        import hashlib
        events = []
        for ev in raw_events:
            title = ev.get("title", "(No Title)")
            agent = ev.get("agent", "Unknown")
            start = ev.get("start", "")
            event_id = hashlib.md5(f"{agent}_{start}_{title}".encode()).hexdigest()
            events.append({
                "id": event_id,
                "agent_name": agent,
                "title": title,
                "start_time": start,
                "end_time": ev.get("end", ""),
                "description": ev.get("description", ""),
                "location": ev.get("location", ""),
                "week_key": wk,
                "is_all_day": ev.get("allDay", False),
                "status": ev.get("status", "confirmed")
            })
        db.upsert_events_bulk(events)
        return jsonify({"synced": len(events), "week": wk})
    
    # Fallback: try server-side fetch
    events = calendar_source.fetch_events(wk)
    db.upsert_events_bulk(events)
    return jsonify({"synced": len(events), "week": wk})

@app.route("/api/sync-redirect", methods=["POST"])
def sync_redirect():
    """Receives form POST from Apps Script redirect with events JSON."""
    import hashlib
    wk = request.form.get("week", current_week_key())
    events_json = request.form.get("events", "[]")
    raw_events = json.loads(events_json)
    
    count = 0
    for ev in raw_events:
        title = ev.get("title", "(No Title)")
        agent = ev.get("agent", "Unknown")
        start = ev.get("start", "")
        event_id = hashlib.md5(f"{agent}_{start}_{title}".encode()).hexdigest()
        db.upsert_event({
            "id": event_id,
            "agent_name": agent,
            "title": title,
            "start_time": start,
            "end_time": ev.get("end", ""),
            "description": ev.get("description", ""),
            "location": ev.get("location", ""),
            "week_key": wk,
            "is_all_day": ev.get("allDay", False),
            "status": ev.get("status", "confirmed")
        })
        count += 1
    
    return redirect(f"/?week={wk}&synced={count}")

@app.route("/api/status", methods=["GET"])
def status():
    wk = request.args.get("week", current_week_key())
    conn = db.get_db()
    cur = conn.cursor()
    ph = "%s" if db._is_pg() else "?"
    cur.execute(f"SELECT COUNT(*) FROM events WHERE week_key={ph}", (wk,))
    total = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM events WHERE week_key={ph} AND classification IS NOT NULL AND classification != ''", (wk,))
    classified = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM events WHERE week_key={ph} AND classification='sales'", (wk,))
    sales = cur.fetchone()[0]
    conn.close()
    return jsonify({"week": wk, "total": total, "classified": classified, "sales": sales, "unclassified": total - classified})

@app.route("/api/trigger-sync", methods=["POST"])
def trigger_sync():
    """UI-facing endpoint: triggers Apps Script to push data (no API key needed)."""
    import requests as req
    data = request.json or {}
    wk = data.get("week", current_week_key())
    apps_url = APP_CONFIG.get("apps_script_url", "")
    if not apps_url:
        return jsonify({"error": "No Apps Script URL configured"}), 500
    try:
        r = req.get(apps_url + "?action=sync&week=" + wk, timeout=90, allow_redirects=True)
        return jsonify({"status": "triggered", "week": wk, "script_response": r.text[:200]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/classify", methods=["POST"])
def classify():
    wk = (request.json or {}).get("week", current_week_key())
    unclassified = db.get_unclassified_events(wk)
    if not unclassified:
        return jsonify({"status": "done", "classified": 0, "remaining": 0})
    
    # Start async classification
    started = classifier.classify_events_async(wk)
    if started:
        return jsonify({"status": "started", "total": len(unclassified)})
    else:
        return jsonify({"status": "already_running", "progress": classifier.get_progress()})

@app.route("/api/classify/progress", methods=["GET"])
def classify_progress():
    progress = classifier.get_progress()
    wk = request.args.get("week", current_week_key())
    remaining = len(db.get_unclassified_events(wk))
    progress["remaining"] = remaining
    return jsonify(progress)

@app.route("/api/sync-classified", methods=["POST"])
def sync_classified():
    """Accept pre-classified events (classified locally before upload)."""
    if not check_api_key():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    wk = data.get("week", current_week_key())
    raw_events = data.get("events", [])
    if not raw_events:
        return jsonify({"error": "no events"}), 400
    
    import hashlib
    events = []
    for ev in raw_events:
        title = ev.get("title", "(No Title)")
        agent = ev.get("agent", "Unknown")
        start = ev.get("start", "")
        event_id = hashlib.md5(f"{agent}_{start}_{title}".encode()).hexdigest()
        events.append({
            "id": event_id,
            "agent_name": agent,
            "title": title,
            "start_time": start,
            "end_time": ev.get("end", ""),
            "description": ev.get("description", ""),
            "location": ev.get("location", ""),
            "week_key": wk,
            "is_all_day": ev.get("allDay", False),
            "status": ev.get("status", "confirmed"),
            "classification": ev.get("classification", ""),
            "confidence": ev.get("confidence", 0),
            "ai_reasoning": ev.get("reasoning", "")
        })
    db.upsert_events_bulk(events)
    
    # Now update classifications directly
    conn = db.get_db()
    cur = conn.cursor()
    ph = "%s" if db._is_pg() else "?"
    updated = 0
    for ev in events:
        if ev["classification"]:
            cur.execute(f"UPDATE events SET classification={ph}, confidence={ph}, ai_reasoning={ph} WHERE id={ph} AND week_key={ph}",
                (ev["classification"], ev["confidence"], ev["ai_reasoning"], ev["id"], wk))
            updated += 1
    conn.commit()
    conn.close()
    return jsonify({"synced": len(events), "classified": updated, "week": wk})

@app.route("/api/override", methods=["POST"])
def override():
    data = request.json
    db.set_override(data["event_id"], data["classification"])
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
