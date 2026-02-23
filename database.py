import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "krs_calendar.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
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
            week_key TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_title TEXT NOT NULL,
            original_classification TEXT,
            corrected_classification TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup ON events(agent_name, title, start_time, week_key);
        CREATE INDEX IF NOT EXISTS idx_events_agent_week ON events(agent_name, week_key);
        CREATE INDEX IF NOT EXISTS idx_events_week ON events(week_key);
    """)
    conn.commit()
    conn.close()

def upsert_event(event):
    conn = get_db()
    conn.execute("""
        INSERT INTO events (id, agent_name, title, start_time, end_time, description, location, week_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_name, title, start_time, week_key) DO UPDATE SET
            end_time=excluded.end_time, description=excluded.description, location=excluded.location
    """, (event['id'], event['agent_name'], event['title'], event['start_time'],
          event.get('end_time',''), event.get('description',''), event.get('location',''), event['week_key']))
    conn.commit()
    conn.close()

def upsert_events_bulk(events):
    """Insert/update many events in a single transaction with retry."""
    import time
    for attempt in range(3):
        try:
            conn = get_db()
            for event in events:
                conn.execute("""
                    INSERT INTO events (id, agent_name, title, start_time, end_time, description, location, week_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(agent_name, title, start_time, week_key) DO UPDATE SET
                        end_time=excluded.end_time, description=excluded.description, location=excluded.location
                """, (event['id'], event['agent_name'], event['title'], event['start_time'],
                      event.get('end_time',''), event.get('description',''), event.get('location',''), event['week_key']))
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 2:
                time.sleep(1)
                continue
            raise

def get_events_for_week(week_key, agent_name=None):
    conn = get_db()
    if agent_name:
        rows = conn.execute("SELECT * FROM events WHERE week_key=? AND agent_name=? ORDER BY start_time", (week_key, agent_name)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM events WHERE week_key=? ORDER BY agent_name, start_time", (week_key,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_unclassified_events(week_key=None):
    conn = get_db()
    if week_key:
        rows = conn.execute("SELECT * FROM events WHERE classification IS NULL AND week_key=?", (week_key,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM events WHERE classification IS NULL").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_classification(event_id, classification, confidence, reasoning=""):
    conn = get_db()
    conn.execute("UPDATE events SET classification=?, confidence=?, ai_reasoning=? WHERE id=?",
                 (classification, confidence, reasoning, event_id))
    conn.commit()
    conn.close()

def set_override(event_id, new_classification):
    conn = get_db()
    event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if event:
        conn.execute("UPDATE events SET override=? WHERE id=?", (new_classification, event_id))
        conn.execute("INSERT INTO overrides (event_title, original_classification, corrected_classification) VALUES (?,?,?)",
                     (event['title'], event['classification'], new_classification))
        conn.commit()
    conn.close()

def get_learned_examples(limit=20):
    conn = get_db()
    rows = conn.execute("SELECT event_title, corrected_classification FROM overrides ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_agent_stats(week_key):
    conn = get_db()
    rows = conn.execute("""
        SELECT agent_name,
            COUNT(*) as total,
            SUM(CASE WHEN COALESCE(override, classification) = 'sales' THEN 1 ELSE 0 END) as sales,
            SUM(CASE WHEN classification IS NULL THEN 1 ELSE 0 END) as unclassified
        FROM events WHERE week_key=? GROUP BY agent_name ORDER BY agent_name
    """, (week_key,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

init_db()
