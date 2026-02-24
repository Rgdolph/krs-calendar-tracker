"""Local relay: receives JSON from browser, saves to file. Fast response."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self, *a):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        wk = body['week']
        events = body['events']
        with open(f'events_cache/{wk}.json', 'w') as f:
            json.dump(events, f)
        print(f'{wk}: saved {len(events)} events', flush=True)
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
    
    def log_message(self, *a): pass

print('Relay on :8765', flush=True)
HTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
