/**
 * KRS Calendar Push — Add this to your existing Apps Script project.
 * 
 * This pushes calendar events to the KRS Calendar App webhook
 * every 15 minutes via a time-based trigger.
 *
 * SETUP:
 * 1. Open your Apps Script project at script.google.com
 * 2. Add this code (new file or paste into existing)
 * 3. Set WEBHOOK_URL to your tunnel URL (see below)
 * 4. Run setupPushTrigger() once to create the 15-min trigger
 * 5. Authorize when prompted
 *
 * The WEBHOOK_URL will be something like:
 *   https://your-tunnel-id.trycloudflare.com/api/webhook
 */

// ============ CONFIGURATION ============
var WEBHOOK_URL = 'https://krs-calendar-tracker.onrender.com/api/webhook';
var WEBHOOK_SECRET = 'krs-cal-push-2026-x9Qm';
// =======================================

/**
 * Push current week + next week events to the webhook.
 * Called by time trigger every 15 minutes.
 */
function pushEvents() {
  var now = new Date();
  
  // Current week bounds (Monday to Sunday)
  var monday = new Date(now);
  monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  monday.setHours(0, 0, 0, 0);
  
  var sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  sunday.setHours(23, 59, 59, 999);
  
  // Next week bounds
  var nextMonday = new Date(monday);
  nextMonday.setDate(monday.getDate() + 7);
  var nextSunday = new Date(nextMonday);
  nextSunday.setDate(nextMonday.getDate() + 6);
  nextSunday.setHours(23, 59, 59, 999);
  
  // Push both weeks
  var currentWeekKey = getWeekKey(monday);
  var nextWeekKey = getWeekKey(nextMonday);
  
  pushWeek(monday, sunday, currentWeekKey);
  pushWeek(nextMonday, nextSunday, nextWeekKey);
}

/**
 * Gather events for a date range and POST to webhook.
 */
function pushWeek(startDate, endDate, weekKey) {
  var events = getAllAgentEvents(startDate, endDate);
  
  if (events.length === 0) {
    Logger.log('No events for ' + weekKey);
    return;
  }
  
  var payload = {
    secret: WEBHOOK_SECRET,
    week: weekKey,
    events: events
  };
  
  var options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    var response = UrlFetchApp.fetch(WEBHOOK_URL, options);
    Logger.log(weekKey + ': ' + response.getResponseCode() + ' — ' + response.getContentText().substring(0, 200));
  } catch (e) {
    Logger.log('Push failed for ' + weekKey + ': ' + e.message);
  }
}

/**
 * Get events from all agent calendars.
 * Uses the same calendar list as your existing script.
 */
function getAllAgentEvents(startDate, endDate) {
  // These match the calendar IDs in config.json
  var calendarIds = [
    'pvogt@krs.insure',
    'mkearns@krs.insure',
    'cjones@krs.insure',
    'dgarza@krs.insure',
    'rlandato@krs.insure',
    'cheeren@krs.insure',
    'zmaa@krs.insure',
    'rdolph@krs.insure',
    'bdailey@krs.insure',
    'cgraybeal@krs.insure',
    'jdaly@krs.insure',
    'jholmes@krs.insure',
    'sburling@krs.insure',
    'kpummill@krs.insure',
    'amacmillan@krs.insure',
    'mseidler@krs.insure',
    'ifuchs@krs.insure'
  ];
  
  var allEvents = [];
  
  for (var i = 0; i < calendarIds.length; i++) {
    try {
      var cal = CalendarApp.getCalendarById(calendarIds[i]);
      if (!cal) continue;
      
      var events = cal.getEvents(startDate, endDate);
      for (var j = 0; j < events.length; j++) {
        var ev = events[j];
        allEvents.push({
          agent: calendarIds[i],
          title: ev.getTitle(),
          start: ev.getStartTime().toISOString(),
          end: ev.getEndTime().toISOString(),
          description: ev.getDescription() || '',
          location: ev.getLocation() || '',
          allDay: ev.isAllDayEvent(),
          status: ev.getMyStatus() ? ev.getMyStatus().toString().toLowerCase() : 'confirmed'
        });
      }
    } catch (e) {
      Logger.log('Error reading calendar ' + calendarIds[i] + ': ' + e.message);
    }
  }
  
  return allEvents;
}

/**
 * Get ISO week key (e.g., "2026-W09") from a date.
 */
function getWeekKey(d) {
  var date = new Date(d.getTime());
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + 3 - (date.getDay() + 6) % 7);
  var week1 = new Date(date.getFullYear(), 0, 4);
  var weekNum = 1 + Math.round(((date.getTime() - week1.getTime()) / 86400000 - 3 + (week1.getDay() + 6) % 7) / 7);
  return date.getFullYear() + '-W' + (weekNum < 10 ? '0' : '') + weekNum;
}

/**
 * Run this ONCE to set up the 15-minute push trigger.
 */
function setupPushTrigger() {
  // Remove any existing push triggers first
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'pushEvents') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  
  // Create new 15-minute trigger
  ScriptApp.newTrigger('pushEvents')
    .timeBased()
    .everyMinutes(15)
    .create();
  
  Logger.log('Push trigger created — events will push every 15 minutes.');
}

/**
 * Manual test — push right now.
 */
function testPush() {
  pushEvents();
}
