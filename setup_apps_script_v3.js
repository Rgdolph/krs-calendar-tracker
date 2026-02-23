// Apps Script v3 — Auto-sync to cloud endpoint
// Set these as Script Properties in Apps Script:
//   SYNC_URL = https://your-app.onrender.com/api/sync
//   SYNC_API_KEY = (matching key set in Render env vars)

function getConfig() {
  var props = PropertiesService.getScriptProperties();
  return {
    syncUrl: props.getProperty('SYNC_URL') || '',
    apiKey: props.getProperty('SYNC_API_KEY') || ''
  };
}

function getISOWeek(d) {
  var date = new Date(d.getTime());
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + 3 - (date.getDay() + 6) % 7);
  var week1 = new Date(date.getFullYear(), 0, 4);
  var weekNum = 1 + Math.round(((date.getTime() - week1.getTime()) / 86400000 - 3 + (week1.getDay() + 6) % 7) / 7);
  var year = date.getFullYear();
  return year + '-W' + (weekNum < 10 ? '0' : '') + weekNum;
}

function getCalendarIds() {
  return [
    {name: "Paul Vogt", id: "pvogt@krs.insure"},
    {name: "Michael Kearns", id: "mkearns@krs.insure"},
    {name: "Christopher Jones", id: "cjones@krs.insure"},
    {name: "Desiree Garza", id: "dgarza@krs.insure"},
    {name: "Robert Landato", id: "rlandato@krs.insure"},
    {name: "Chad Heeren", id: "cheeren@krs.insure"},
    {name: "Zachary Maa", id: "zmaa@krs.insure"},
    {name: "Ryan Dolph", id: "rdolph@krs.insure"},
    {name: "Brandon Dailey", id: "bdailey@krs.insure"},
    {name: "Caleb Graybeal", id: "cgraybeal@krs.insure"},
    {name: "Joy Daly", id: "jdaly@krs.insure"},
    {name: "Jeorge Holmes", id: "jholmes@krs.insure"},
    {name: "Stephanie Burling", id: "sburling@krs.insure"},
    {name: "Kevin Pummill", id: "kpummill@krs.insure"},
    {name: "Toño Macmillan", id: "amacmillan@krs.insure"},
    {name: "Mike Seidler", id: "mseidler@krs.insure"},
    {name: "Iris Fuchs", id: "ifuchs@krs.insure"}
  ];
}

function fetchWeekEvents(weekOffset) {
  var today = new Date();
  var dayOfWeek = today.getDay();
  var monday = new Date(today);
  monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1) + (weekOffset * 7));
  monday.setHours(0, 0, 0, 0);
  var sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  sunday.setHours(23, 59, 59, 999);
  
  var weekKey = getISOWeek(monday);
  var calendars = getCalendarIds();
  var allEvents = [];
  
  for (var i = 0; i < calendars.length; i++) {
    try {
      var cal = CalendarApp.getCalendarById(calendars[i].id);
      if (!cal) continue;
      var events = cal.getEvents(monday, sunday);
      for (var j = 0; j < events.length; j++) {
        var ev = events[j];
        allEvents.push({
          agent: calendars[i].name,
          title: ev.getTitle() || "(No Title)",
          start: ev.getStartTime().toISOString(),
          end: ev.getEndTime().toISOString(),
          description: (ev.getDescription() || "").substring(0, 500),
          location: ev.getLocation() || "",
          allDay: ev.isAllDayEvent(),
          status: ev.getMyStatus ? String(ev.getMyStatus()) : "confirmed"
        });
      }
    } catch (e) {
      Logger.log("Error reading " + calendars[i].name + ": " + e);
    }
  }
  
  return {week: weekKey, events: allEvents};
}

// Push events to cloud endpoint
function pushToCloud(weekData) {
  var config = getConfig();
  if (!config.syncUrl) {
    Logger.log("No SYNC_URL configured in Script Properties");
    return {error: "No SYNC_URL configured"};
  }
  
  var payload = {
    week: weekData.week,
    events: weekData.events,
    api_key: config.apiKey
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  var response = UrlFetchApp.fetch(config.syncUrl, options);
  var code = response.getResponseCode();
  var body = response.getContentText();
  Logger.log("Push response (" + code + "): " + body);
  return {code: code, body: body};
}

// Sync current week — called by time trigger
function syncCurrentWeek() {
  var data = fetchWeekEvents(0);
  var result = pushToCloud(data);
  
  // Also trigger classification
  var config = getConfig();
  if (config.syncUrl) {
    var classifyUrl = config.syncUrl.replace('/api/sync', '/api/classify');
    UrlFetchApp.fetch(classifyUrl, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify({week: data.week, api_key: config.apiKey}),
      muteHttpExceptions: true
    });
  }
  
  Logger.log("Synced " + data.events.length + " events for " + data.week);
}

// Sync last week too (for late entries)
function syncLastWeek() {
  var data = fetchWeekEvents(-1);
  pushToCloud(data);
  Logger.log("Synced " + data.events.length + " events for " + data.week);
}

// Manual: sync both weeks
function syncAll() {
  syncCurrentWeek();
  syncLastWeek();
}

// Keep existing doGet for backward compatibility
function doGet(e) {
  var weekOffset = 0;
  if (e && e.parameter && e.parameter.week_offset) {
    weekOffset = parseInt(e.parameter.week_offset) || 0;
  }
  var data = fetchWeekEvents(weekOffset);
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
