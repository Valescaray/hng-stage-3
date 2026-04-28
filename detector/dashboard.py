import time
import json
import threading
import psutil
from http.server import BaseHTTPRequestHandler, HTTPServer

class DashboardServer:
    def __init__(self, host, port, state):
        self.state = state   # shared dict updated by main loop
        self.server = HTTPServer((host, port), self._make_handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def _make_handler(self):
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass  # suppress access logs

            def do_GET(self):
                if self.path == '/metrics':
                    self._send_json(state)
                else:
                    self._send_html()

            def _send_json(self, data):
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(body)

            def _send_html(self):
                html = DASHBOARD_HTML
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(html.encode())

        return Handler


DASHBOARD_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>HNG Anomaly Detector</title>
<meta http-equiv="refresh" content="3">
<style>
  body { font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 20px; margin: 0; }
  h1 { color: #58a6ff; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card h3 { margin: 0 0 8px; color: #79c0ff; font-size: 13px; text-transform: uppercase; }
  .metric { font-size: 28px; font-weight: bold; color: #f0f6fc; }
  .banned-ip { color: #f85149; padding: 2px 0; }
  .top-ip { padding: 2px 0; display: flex; justify-content: space-between; }
  .uptime { color: #3fb950; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  td { padding: 4px 8px; border-bottom: 1px solid #21262d; }
</style>
</head><body>
<h1>HNG Anomaly Detector — Live</h1>
<p id="ts" style="color:#8b949e"></p>
<div class="grid">
  <div class="card"><h3>Global req/s</h3><div class="metric" id="rps">-</div></div>
  <div class="card"><h3>Baseline mean</h3><div class="metric" id="mean">-</div></div>
  <div class="card"><h3>Baseline stddev</h3><div class="metric" id="std">-</div></div>
  <div class="card"><h3>CPU / Memory</h3><div class="metric" id="sys">-</div></div>
  <div class="card"><h3>Uptime</h3><div class="metric uptime" id="up">-</div></div>
  <div class="card"><h3>Banned IPs</h3><div id="bans">none</div></div>
  <div class="card" style="grid-column: span 2"><h3>Top 10 source IPs (last 60s)</h3>
    <div id="topips"></div></div>
</div>
<script>
async function refresh() {
  try {
    const r = await fetch('/metrics');
    const d = await r.json();
    document.getElementById('rps').textContent = d.global_rps?.toFixed(2) ?? '-';
    document.getElementById('mean').textContent = d.baseline_mean?.toFixed(3) ?? '-';
    document.getElementById('std').textContent = d.baseline_stddev?.toFixed(3) ?? '-';
    document.getElementById('sys').textContent = `CPU ${d.cpu_pct}% | MEM ${d.mem_pct}%`;
    document.getElementById('up').textContent = d.uptime ?? '-';
    document.getElementById('ts').textContent = 'Last updated: ' + new Date().toISOString();
    const bansEl = document.getElementById('bans');
    if (d.banned_ips?.length) {
      bansEl.innerHTML = d.banned_ips.map(b =>
        `<div class="banned-ip">🚫 ${b.ip} — ${b.remaining}s left</div>`).join('');
    } else { bansEl.textContent = 'none'; }
    const tipsEl = document.getElementById('topips');
    if (d.top_ips?.length) {
      tipsEl.innerHTML = '<table>' + d.top_ips.map((t,i) =>
        `<tr><td>${i+1}. ${t.ip}</td><td>${t.rate?.toFixed(2)} req/s</td></tr>`).join('') + '</table>';
    }
  } catch(e) {}
}
refresh();
setInterval(refresh, 3000);
</script>
</body></html>"""
