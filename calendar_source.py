import json
import os
import sys
import time
import hashlib
import csv
import io
import requests
from datetime import datetime, date, timedelta

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def get_week_bounds(week_key):
    """week_key = 'YYYY-Www' e.g. '2026-W09'. Returns (monday, sunday) as date objects."""
    year, week = int(week_key[:4]), int(week_key.split('W')[1])
    monday = date.fromisocalendar(year, week, 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday

def fetch_events(week_key):
    """Fetch events from Google Sheet (published CSV) and filter to the requested week."""
    config = load_config()
    source = config.get("data_source", "sheet")
    
    if source == "manual":
        return fetch_from_manual_json(week_key)
    
    # Default: read from Google Sheet
    return fetch_from_sheet(week_key)

def fetch_from_sheet(week_key):
    """Read events from the published Google Sheet RawEvents tab."""
    config = load_config()
    sheet_id = config.get("google_sheet_id", "1uM22f664QVtHneL53nsmv5mHaJRmMWrLsQFEtvcMbxw")
    
    # Published CSV URL — works when sheet is shared as "Anyone with the link"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=RawEvents"
    
    print(f"[sync] Fetching from Sheet for {week_key}...", flush=True)
    resp = requests.get(url, timeout=30)
    
    if resp.status_code != 200:
        raise Exception(f"Failed to read Sheet (HTTP {resp.status_code}). Make sure the sheet is shared as 'Anyone with the link'.")
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(resp.text))
    
    monday, sunday = get_week_bounds(week_key)
    events = []
    
    for row in reader:
        try:
            # Parse start time to check if it falls in the requested week
            start_str = row.get("start", "")
            if not start_str:
                continue
            
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            event_date = start_dt.date()
            
            if event_date < monday or event_date > sunday:
                continue
            
            title = row.get("title", "(No Title)")
            agent = row.get("agent", "Unknown")
            
            # Generate stable ID from agent + start + title
            event_id = hashlib.md5(f"{agent}_{start_str}_{title}".encode()).hexdigest()
            
            events.append({
                "id": event_id,
                "agent_name": agent,
                "title": title,
                "start_time": start_str,
                "end_time": row.get("end", ""),
                "description": row.get("description", ""),
                "location": row.get("location", ""),
                "week_key": week_key,
                "is_all_day": row.get("allDay", "").upper() == "TRUE",
                "status": row.get("status", "confirmed")
            })
        except Exception as e:
            print(f"[sync] Skipping row: {e}", flush=True)
            continue
    
    print(f"[sync] Got {len(events)} events for {week_key}", flush=True)
    return events

def fetch_from_manual_json(week_key):
    """Load events from a local JSON file (for testing)."""
    path = os.path.join(os.path.dirname(__file__), "sample_events.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return [item for item in data if item.get("week_key") == week_key or not item.get("week_key")]
