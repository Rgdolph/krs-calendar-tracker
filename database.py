"""
Database layer for KRS Calendar Tracker.
Uses Supabase REST API when SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set,
otherwise falls back to local SQLite for development.
"""
import os
import json
import requests
from datetime import datetime

# Supabase REST API config
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Table names
EVENTS_TABLE = os.environ.get("EVENTS_TABLE", "calendar_events")
OVERRIDES_TABLE = os.environ.get("OVERRIDES_TABLE", "calendar_overrides")

# Legacy Postgres support (kept for local dev with SQLite)
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def _use_rest():
    """Use Supabase REST API if credentials are available."""
    return bool(SUPABASE_URL and SUPABASE_KEY)

def _headers(prefer="return=minimal"):
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }

def _rest_get(table, params=""):
    """GET from Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    r = requests.get(url, headers=_headers("return=representation"))
    r.raise_for_status()
    return r.json()

def _rest_post(table, data, upsert=False):
    """POST to Supabase REST API."""
    prefer = "return=minimal,resolution=merge-duplicates" if upsert else "return=minimal"
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=_headers(prefer), json=data)
    r.raise_for_status()
    return r

def _rest_patch(table, data, filter_str):
    """PATCH (update) rows in Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter_str}"
    r = requests.patch(url, headers=_headers("return=minimal"), json=data)
    r.raise_for_status()
    return r

def _rest_delete(table, filter_str):
    """DELETE rows from Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter_str}"
    r = requests.delete(url, headers=_headers("return=minimal"))
    r.raise_for_status()
    return r

# ── SQLite fallback (local dev) ──────────────────────────────────────────

def _get_sqlite():
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), "krs_calendar.db")
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def _fetchall_dicts(cursor):
    if not cursor.description:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

# ── Init ─────────────────────────────────────────────────────────────────

def init_db():
    """Initialize database tables. For REST API mode, tables must exist in Supabase already."""
    if _use_rest():
        # Tables already created via SQL editor — just verify connectivity
        try:
            r = requests.get(f"{SUPABASE_URL}/rest/v1/{EVENTS_TABLE}?limit=1",
                           headers=_headers(), timeout=10)
            r.raise_for_status()
            print(f"[DB] Supabase REST API connected — table '{EVENTS_TABLE}' OK", flush=True)
        except Exception as e:
            print(f"[DB] WARNING: Supabase REST API check failed: {e}", flush=True)
        return

    # SQLite fallback
    conn = _get_sqlite()
    cur = conn.cursor()
    cur.executescript(f"""
        CREATE TABLE IF NOT EXISTS {EVENTS_TABLE} (
            id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            description TEXT DEFAULT '',
            location TEXT DEFAULT '',
            classification TEXT DEFAULT NULL,
            confidence REAL DEFAULT NULL,
            ai_reasoning TEXT DEFAULT '',
            override TEXT DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            week_key TEXT NOT NULL,
            content_hash TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS {OVERRIDES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_title TEXT NOT NULL,
            original_classification TEXT,
            corrected_classification TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_cal_events_dedup ON {EVENTS_TABLE}(agent_name, title, start_time, week_key);
        CREATE INDEX IF NOT EXISTS idx_cal_events_agent_week ON {EVENTS_TABLE}(agent_name, week_key);
        CREATE INDEX IF NOT EXISTS idx_cal_events_week ON {EVENTS_TABLE}(week_key);
    """)
    conn.commit()
    conn.close()

# ── Upsert ───────────────────────────────────────────────────────────────

def upsert_event(event):
    if _use_rest():
        row = {
            "id": event["id"],
            "agent_name": event["agent_name"],
            "title": event["title"],
            "start_time": event["start_time"],
            "end_time": event.get("end_time", ""),
            "description": event.get("description", ""),
            "location": event.get("location", ""),
            "week_key": event["week_key"],
        }
        _rest_post(EVENTS_TABLE, row, upsert=True)
        return

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO {EVENTS_TABLE} (id, agent_name, title, start_time, end_time, description, location, week_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_name, title, start_time, week_key) DO UPDATE SET
            end_time=excluded.end_time, description=excluded.description, location=excluded.location
    """, (event['id'], event['agent_name'], event['title'], event['start_time'],
          event.get('end_time',''), event.get('description',''), event.get('location',''), event['week_key']))
    conn.commit()
    conn.close()

def upsert_events_bulk(events):
    """Insert/update many events."""
    if _use_rest():
        rows = []
        for event in events:
            rows.append({
                "id": event["id"],
                "agent_name": event["agent_name"],
                "title": event["title"],
                "start_time": event["start_time"],
                "end_time": event.get("end_time", ""),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "week_key": event["week_key"],
                "content_hash": event.get("content_hash", ""),
            })
        # Batch in groups of 500
        for i in range(0, len(rows), 500):
            _rest_post(EVENTS_TABLE, rows[i:i+500], upsert=True)
        return

    conn = _get_sqlite()
    cur = conn.cursor()
    for event in events:
        cur.execute(f"""
            INSERT INTO {EVENTS_TABLE} (id, agent_name, title, start_time, end_time, description, location, week_key, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_name, title, start_time, week_key) DO UPDATE SET
                end_time=excluded.end_time, description=excluded.description,
                location=excluded.location, content_hash=excluded.content_hash
        """, (event['id'], event['agent_name'], event['title'], event['start_time'],
              event.get('end_time',''), event.get('description',''), event.get('location',''),
              event['week_key'], event.get('content_hash', '')))
    conn.commit()
    conn.close()

# ── Queries ──────────────────────────────────────────────────────────────

def get_event_hashes_for_week(week_key):
    """Return dict of {event_id: content_hash} for a given week."""
    if _use_rest():
        rows = _rest_get(EVENTS_TABLE, f"select=id,content_hash&week_key=eq.{week_key}")
        return {r["id"]: (r.get("content_hash") or "") for r in rows}

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"SELECT id, content_hash FROM {EVENTS_TABLE} WHERE week_key=?", (week_key,))
    result = {row[0]: (row[1] or '') for row in cur.fetchall()}
    conn.close()
    return result

def get_event_ids_for_week(week_key):
    """Return a set of event IDs for a given week."""
    if _use_rest():
        rows = _rest_get(EVENTS_TABLE, f"select=id&week_key=eq.{week_key}")
        return {r["id"] for r in rows}

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM {EVENTS_TABLE} WHERE week_key=?", (week_key,))
    ids = {row[0] for row in cur.fetchall()}
    conn.close()
    return ids

def get_events_for_week(week_key, agent_name=None):
    if _use_rest():
        params = f"week_key=eq.{week_key}&order=agent_name,start_time"
        if agent_name:
            from urllib.parse import quote
            params = f"week_key=eq.{week_key}&agent_name=eq.{quote(agent_name)}&order=start_time"
        return _rest_get(EVENTS_TABLE, params)

    conn = _get_sqlite()
    cur = conn.cursor()
    if agent_name:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE week_key=? AND agent_name=? ORDER BY start_time", (week_key, agent_name))
    else:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE week_key=? ORDER BY agent_name, start_time", (week_key,))
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

def get_unclassified_events(week_key=None):
    if _use_rest():
        params = "classification=is.null"
        if week_key:
            params += f"&week_key=eq.{week_key}"
        return _rest_get(EVENTS_TABLE, params)

    conn = _get_sqlite()
    cur = conn.cursor()
    if week_key:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE classification IS NULL AND week_key=?", (week_key,))
    else:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE classification IS NULL")
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

def update_classification(event_id, classification, confidence, reasoning=""):
    if _use_rest():
        _rest_patch(EVENTS_TABLE, {
            "classification": classification,
            "confidence": confidence,
            "ai_reasoning": reasoning,
        }, f"id=eq.{event_id}")
        return

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"UPDATE {EVENTS_TABLE} SET classification=?, confidence=?, ai_reasoning=? WHERE id=?",
                (classification, confidence, reasoning, event_id))
    conn.commit()
    conn.close()

def set_override(event_id, new_classification):
    if _use_rest():
        # Get the event first
        rows = _rest_get(EVENTS_TABLE, f"id=eq.{event_id}")
        if rows:
            event = rows[0]
            _rest_patch(EVENTS_TABLE, {"override": new_classification}, f"id=eq.{event_id}")
            _rest_post(OVERRIDES_TABLE, {
                "event_title": event["title"],
                "original_classification": event.get("classification"),
                "corrected_classification": new_classification,
            })
        return

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE id=?", (event_id,))
    row = cur.fetchone()
    if row:
        event = dict(zip([d[0] for d in cur.description], row)) if not isinstance(row, dict) else row
        cur.execute(f"UPDATE {EVENTS_TABLE} SET override=? WHERE id=?", (new_classification, event_id))
        cur.execute(f"INSERT INTO {OVERRIDES_TABLE} (event_title, original_classification, corrected_classification) VALUES (?,?,?)",
                    (event['title'], event['classification'], new_classification))
        conn.commit()
    conn.close()

def get_learned_examples(limit=20):
    if _use_rest():
        return _rest_get(OVERRIDES_TABLE, f"select=event_title,corrected_classification&order=created_at.desc&limit={limit}")

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"SELECT event_title, corrected_classification FROM {OVERRIDES_TABLE} ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

def get_agent_stats(week_key):
    if _use_rest():
        # Fetch all events for the week and compute stats in Python
        events = _rest_get(EVENTS_TABLE, f"select=agent_name,classification,override&week_key=eq.{week_key}")
        stats = {}
        for e in events:
            name = e["agent_name"]
            if name not in stats:
                stats[name] = {"agent_name": name, "total": 0, "sales": 0, "unclassified": 0}
            stats[name]["total"] += 1
            effective = e.get("override") or e.get("classification")
            if effective == "sales":
                stats[name]["sales"] += 1
            if not e.get("classification"):
                stats[name]["unclassified"] += 1
        return sorted(stats.values(), key=lambda x: x["agent_name"])

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT agent_name,
            COUNT(*) as total,
            SUM(CASE WHEN COALESCE(override, classification) = 'sales' THEN 1 ELSE 0 END) as sales,
            SUM(CASE WHEN classification IS NULL THEN 1 ELSE 0 END) as unclassified
        FROM {EVENTS_TABLE} WHERE week_key=? GROUP BY agent_name ORDER BY agent_name
    """, (week_key,))
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

# ── Status helpers (used by app.py) ──────────────────────────────────────

def get_week_counts(week_key):
    """Return (total, classified, sales) counts for a week."""
    if _use_rest():
        events = _rest_get(EVENTS_TABLE, f"select=classification&week_key=eq.{week_key}")
        total = len(events)
        classified = sum(1 for e in events if e.get("classification"))
        sales = sum(1 for e in events if e.get("classification") == "sales")
        return total, classified, sales

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {EVENTS_TABLE} WHERE week_key=?", (week_key,))
    total = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {EVENTS_TABLE} WHERE week_key=? AND classification IS NOT NULL AND classification != ''", (week_key,))
    classified = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {EVENTS_TABLE} WHERE week_key=? AND classification='sales'", (week_key,))
    sales = cur.fetchone()[0]
    conn.close()
    return total, classified, sales

# ── Bulk classification update (used by app.py sync) ─────────────────────

def update_classification_by_id_week(event_id, week_key, classification, confidence, reasoning):
    """Update classification for a specific event by id + week_key."""
    if _use_rest():
        _rest_patch(EVENTS_TABLE, {
            "classification": classification,
            "confidence": confidence,
            "ai_reasoning": reasoning,
        }, f"id=eq.{event_id}&week_key=eq.{week_key}")
        return

    conn = _get_sqlite()
    cur = conn.cursor()
    cur.execute(f"UPDATE {EVENTS_TABLE} SET classification=?, confidence=?, ai_reasoning=? WHERE id=? AND week_key=?",
                (classification, confidence, reasoning, event_id, week_key))
    conn.commit()
    conn.close()

init_db()
