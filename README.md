# KRS Calendar Appointment Tracker

Sales appointment tracker for Key Retirement Solutions. Pulls agent calendar events, classifies them as sales/not-sales using AI, and provides a dashboard view.

## Quick Start

```bash
cd krs-calendar-app
pip install -r requirements.txt
python app.py
```

Open http://localhost:5050

## Sample Data

The app ships with `sample_events.json` for testing. Config is set to `"data_source": "manual"` by default. Click **Sync Calendars** to load sample events, then **Classify All** to run AI classification.

## Data Sources

Edit `config.json` `"data_source"` to one of:

### 1. `"manual"` (default)
Reads from `sample_events.json`. Good for testing.

### 2. `"apps_script"` (recommended)
Uses your existing Google Apps Script access to calendars:
1. Open [script.google.com](https://script.google.com) → new project
2. Paste contents of `setup_apps_script.js`
3. Update the CALENDARS array with your agents
4. Deploy → Web app (Execute as: Me, Access: Anyone)
5. Copy the URL into `config.json` → `"apps_script_url"`
6. Set `"data_source": "apps_script"`

### 3. `"google_api"`
Direct Google Calendar API with service account:
1. Create a GCP project, enable Calendar API
2. Create a service account, download JSON key as `service_account.json`
3. Share each agent's calendar with the service account email
4. Set `"data_source": "google_api"`

## Usage

- **Sync Calendars** – pulls events for the displayed week
- **Classify All** – runs GPT-4o-mini on unclassified events
- Click an agent card to see their appointments
- 🔄 button toggles sales/not-sales (override stored for AI learning)
- Week navigation with ← → buttons

## Color Coding
- 🟢 Green border = Sales appointment
- ⬜ Gray border = Not sales
- 🟡 Yellow border = Unclassified
- ✏️ = Manually overridden
