// Extract a chunk of events from the loaded page
// Usage: pass start and count as arguments
// Returns: JSON array of compact events
(start, count) => {
    const events = JSON.parse(document.body.innerText).events;
    const chunk = events.slice(start, start + count);
    return JSON.stringify(chunk.map(e => ({
        agent: e.agent,
        title: e.title,
        start: e.start,
        end: e.end,
        description: e.description || '',
        location: e.location || ''
    })));
}
