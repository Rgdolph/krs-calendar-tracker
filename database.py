import os
import json
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Table names (configurable for different backends)
EVENTS_TABLE = os.environ.get("EVENTS_TABLE", "calendar_events")
OVERRIDES_TABLE = os.environ.get("OVERRIDES_TABLE", "calendar_overrides")

def get_db():
    """Get a PostgreSQL connection (or fall back to SQLite for local dev)."""
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        DB_PATH = os.path.join(os.path.dirname(__file__), "krs_calendar.db")
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

def _is_pg():
    return bool(DATABASE_URL)

def _dict_row(row, cursor=None):
    """Convert a row to dict for both SQLite and PostgreSQL."""
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        return dict(row)
    if cursor and cursor.description:
        return {desc[0]: val for desc, val in zip(cursor.description, row)}
    return dict(row)

def _fetchall_dicts(cursor):
    if not cursor.description:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def init_db():
    conn = get_db()
    cur = conn.cursor()
    if _is_pg():
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {EVENTS_TABLE} (
                id TEXT,
                agent_name TEXT NOT NULL,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT DEFAULT '',
                description TEXT DEFAULT '',
                location TEXT DEFAULT '',
                classification TEXT DEFAULT NULL,
                confidence REAL DEFAULT NULL,
                ai_reasoning TEXT DEFAULT '',
                override TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                week_key TEXT NOT NULL,
                content_hash TEXT DEFAULT ''
            )
        """)
        cur.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cal_events_dedup 
            ON {EVENTS_TABLE}(agent_name, title, start_time, week_key)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_cal_events_agent_week ON {EVENTS_TABLE}(agent_name, week_key)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_cal_events_week ON {EVENTS_TABLE}(week_key)
        """)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {OVERRIDES_TABLE} (
                id SERIAL PRIMARY KEY,
                event_title TEXT NOT NULL,
                original_classification TEXT,
                corrected_classification TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    else:
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
    # Migration: add content_hash column if missing (existing DBs)
    try:
        if _is_pg():
            cur.execute(f"ALTER TABLE {EVENTS_TABLE} ADD COLUMN content_hash TEXT DEFAULT ''")
            conn.commit()
        else:
            cur.execute(f"ALTER TABLE {EVENTS_TABLE} ADD COLUMN content_hash TEXT DEFAULT ''")
            conn.commit()
    except Exception:
        conn.rollback() if _is_pg() else None  # column already exists
    conn.close()

def upsert_event(event):
    conn = get_db()
    cur = conn.cursor()
    if _is_pg():
        cur.execute(f"""
            INSERT INTO {EVENTS_TABLE} (id, agent_name, title, start_time, end_time, description, location, week_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(agent_name, title, start_time, week_key) DO UPDATE SET
                end_time=EXCLUDED.end_time, description=EXCLUDED.description, location=EXCLUDED.location
        """, (event['id'], event['agent_name'], event['title'], event['start_time'],
              event.get('end_time',''), event.get('description',''), event.get('location',''), event['week_key']))
    else:
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
    """Insert/update many events in a single transaction."""
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    conflict_ref = "EXCLUDED" if _is_pg() else "excluded"
    for event in events:
        cur.execute(f"""
            INSERT INTO {EVENTS_TABLE} (id, agent_name, title, start_time, end_time, description, location, week_key, content_hash)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ON CONFLICT(agent_name, title, start_time, week_key) DO UPDATE SET
                end_time={conflict_ref}.end_time, description={conflict_ref}.description,
                location={conflict_ref}.location, content_hash={conflict_ref}.content_hash
        """, (event['id'], event['agent_name'], event['title'], event['start_time'],
              event.get('end_time',''), event.get('description',''), event.get('location',''),
              event['week_key'], event.get('content_hash', '')))
    conn.commit()
    conn.close()

def get_event_hashes_for_week(week_key):
    """Return dict of {event_id: content_hash} for a given week."""
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    cur.execute(f"SELECT id, content_hash FROM {EVENTS_TABLE} WHERE week_key={ph}", (week_key,))
    result = {row[0]: (row[1] or '') for row in cur.fetchall()}
    conn.close()
    return result

def get_event_ids_for_week(week_key):
    """Return a set of event IDs for a given week (fast lookup for dedup)."""
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    cur.execute(f"SELECT id FROM {EVENTS_TABLE} WHERE week_key={ph}", (week_key,))
    ids = {row[0] for row in cur.fetchall()}
    conn.close()
    return ids

def get_events_for_week(week_key, agent_name=None):
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    if agent_name:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE week_key={ph} AND agent_name={ph} ORDER BY start_time", (week_key, agent_name))
    else:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE week_key={ph} ORDER BY agent_name, start_time", (week_key,))
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

def get_unclassified_events(week_key=None):
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    if week_key:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE classification IS NULL AND week_key={ph}", (week_key,))
    else:
        cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE classification IS NULL")
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

def update_classification(event_id, classification, confidence, reasoning=""):
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    cur.execute(f"UPDATE {EVENTS_TABLE} SET classification={ph}, confidence={ph}, ai_reasoning={ph} WHERE id={ph}",
                (classification, confidence, reasoning, event_id))
    conn.commit()
    conn.close()

def set_override(event_id, new_classification):
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    cur.execute(f"SELECT * FROM {EVENTS_TABLE} WHERE id={ph}", (event_id,))
    row = cur.fetchone()
    if row:
        event = dict(zip([d[0] for d in cur.description], row)) if not isinstance(row, dict) else row
        cur.execute(f"UPDATE {EVENTS_TABLE} SET override={ph} WHERE id={ph}", (new_classification, event_id))
        cur.execute(f"INSERT INTO {OVERRIDES_TABLE} (event_title, original_classification, corrected_classification) VALUES ({ph},{ph},{ph})",
                    (event['title'], event['classification'], new_classification))
        conn.commit()
    conn.close()

def get_learned_examples(limit=20):
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    cur.execute(f"SELECT event_title, corrected_classification FROM {OVERRIDES_TABLE} ORDER BY created_at DESC LIMIT {ph}", (limit,))
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

def get_agent_stats(week_key):
    conn = get_db()
    cur = conn.cursor()
    ph = "%s" if _is_pg() else "?"
    cur.execute(f"""
        SELECT agent_name,
            COUNT(*) as total,
            SUM(CASE WHEN COALESCE(override, classification) = 'sales' THEN 1 ELSE 0 END) as sales,
            SUM(CASE WHEN classification IS NULL THEN 1 ELSE 0 END) as unclassified
        FROM {EVENTS_TABLE} WHERE week_key={ph} GROUP BY agent_name ORDER BY agent_name
    """, (week_key,))
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows

init_db()
