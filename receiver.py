"""Local HTTP server to receive JSON data from browser."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        data = self.rfile.read(length)
        
        # Extract week from path like /save/2026-W02
        week = self.path.split('/')[-1]
        filepath = f"events_cache/{week}.json"
        
        with open(filepath, 'wb') as f:
            f.write(data)
        
        parsed = json.loads(data)
        count = len(parsed.get('events', parsed) if isinstance(parsed, dict) else parsed)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"saved": filepath, "count": count}).encode())
        print(f"Saved {count} events to {filepath}")
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

print("Starting receiver on port 9876...")
HTTPServer(('127.0.0.1', 9876), Handler).serve_forever()
