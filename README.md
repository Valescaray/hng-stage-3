# HNG Stage 3 — Anomaly Detector Stack

A Docker Compose stack that deploys **Nextcloud** behind **Nginx**, with a **Python detector daemon** that monitors access logs in real-time, detects traffic anomalies using a statistical baseline, bans offending IPs via `iptables`, and exposes a live dashboard.

---

## Live Access Details

**Server IP:** `[3.228.58.14]` (active during grading)

**Dashboard URL:** `https://monitor.oppsdev.xyz`

**GitHub Repository:** [HNG-STAGE-3](https://github.com/Valescaray/hng-stage-3) _(public)_

**Blog Post:** [How i built a real time ddos detection engine from scratch](https://dev.to/chukwudum_agbasi_d9e1cb29/how-i-built-a-real-time-ddos-detection-engine-from-scratch-no-fail2ban-5fl4)

---

## Language Choice: Python

**Why Python?**

- **Rapid iteration speed**: Quick to prototype, test, and deploy anomaly detection logic
- **Rich stdlib**: `collections.deque` for efficient sliding window; `statistics` module for mean/stddev calculations
- **System metrics**: `psutil` for fine-grained access to system state during anomaly conditions
- **Readability**: Clear, maintainable code for statistical algorithms crucial in production
- **expertise**: I have more experience with Python, which enables faster development and higher code quality compared to alternatives such as Go

---

## How the Sliding Window Works

The **per-IP request rate** is tracked using a **deque of `(timestamp, is_error)` tuples**:

```python
from collections import deque

per_ip_window = deque()  # [(timestamp, is_error), ...]

# On every new request:
now = time.time()
per_ip_window.append((now, is_error_response))

# Remove old entries (older than 60 seconds):
while per_ip_window and per_ip_window[0][0] < now - 60:
    per_ip_window.popleft()

# Calculate rate (requests per second):
rate = len(per_ip_window) / 60
```

- **Efficiency**: `popleft()` is O(1); perfect for sliding windows
- **Real-time**: Rate updates instantly as requests arrive
- **Memory-safe**: Old entries auto-expire; no unbounded growth

---

## How the Baseline Works

The **baseline** is a **30-minute rolling window of per-second request counts**, recalculated every 60 seconds:

```python
# Maintained over a 30-minute (1800-second) window
baseline_window = deque(maxlen=1800)  # per-second counts

# Every 60 seconds:
def recalculate_baseline():
    if len(baseline_window) >= 100:  # Need at least ~1.5 min of data
        mean = statistics.mean(baseline_window)
        stddev = statistics.stdev(baseline_window)
    else:
        mean, stddev = 0, 0
```

**Key design decisions:**

- **Per-hour slots** (optional granularity): Capture peak times separately; richer recent picture
- **Mean/stddev from scratch**: Fresh calculation each cycle; adapts quickly to traffic pattern shifts
- **Floor prevention**: If mean would collapse near zero (e.g., `0.001`), use floor of `1.0` to prevent false positives on quiet servers
- **30-minute window**: Long enough for stable statistics; short enough to respond to gradual shifts

**Example:**

- Baseline mean: 50 req/s, stddev: 5
- Per-IP threshold: `z ≥ 3.0` → bans at 50 + 3×5 = 65 req/s
- Rate multiplier threshold: `5× baseline` → bans at 250 req/s

---

## Architecture

```
Internet → Nginx (:80) → Nextcloud → MariaDB
                ↓ (shared volume: HNG-nginx-logs)
           Detector Daemon
             ├── LogMonitor   – tails hng-access.log
             ├── BaselineTracker – rolling 30-min mean/stddev
             ├── AnomalyDetector – per-IP & global z-score / rate multiplier
             ├── Blocker      – iptables DROP rules
             ├── Unbanner     – backoff schedule (10m→30m→2h→permanent)
             ├── SlackNotifier – webhook alerts
             ├── AuditLogger  – /var/log/detector/audit.log
             └── DashboardServer – HTTP UI on :8080
```

See `docs/architecture.png` for the visual diagram.

---

## Project Structure

```
project/
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
├── detector/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.yaml
│   ├── main.py
│   ├── monitor.py
│   ├── baseline.py
│   ├── detector.py
│   ├── blocker.py
│   ├── unbanner.py
│   ├── notifier.py
│   ├── dashboard.py
│   └── audit.py
├── docs/
│   └── architecture.png
├── screenshots/
└── README.md
```

---

## Setup Instructions: From Fresh VPS to Running Stack

### Prerequisites

- **OS**: Linux (Ubuntu 22.04 LTS or similar) — `iptables` required for blocking
- **Network**: Inbound HTTP (port 80) and HTTPS (port 443) open; Slack webhook network access
- **Software**:
  ```bash
  sudo apt update && sudo apt install -y docker.io docker-compose git
  sudo usermod -aG docker $USER
  newgrp docker
  ```

### Step 1: Clone & Configure

```bash
git clone https://github.com/yourusername/HNG-STAGE-3.git
cd HNG-STAGE-3
```

**Create `.env` file:**

```bash
cp .env.example .env
nano .env
```

Fill in:

```env
TRUSTED_DOMAINS=YOUR_SERVER_IP your.domain.com
ADMIN_USER=admin
ADMIN_PASSWORD=your_secure_password
DB_PASSWORD=your_db_password
DB_ROOT_PASSWORD=your_root_password
SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
DRY_RUN=false  # Set to "false" for production; "true" for testing
```

**Update `detector/config.yaml`:**

```yaml
slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
baseline_recalc_interval_seconds: 60
z_score_threshold: 3.0
rate_multiplier_threshold: 5.0
```

### Step 2: Start the Stack

```bash
docker compose up -d --build
```

**Verify services:**

```bash
docker compose ps
# All containers should be running: nginx, nextcloud, mariadb, detector
```

### Step 3: Check Logs

**Nginx access log (JSON format):**

```bash
docker exec $(docker compose ps -q nginx) tail -f /var/log/nginx/hng-access.log
```

**Detector logs:**

```bash
docker logs $(docker compose ps -q detector) --follow
```

**Audit log:**

```bash
docker exec $(docker compose ps -q detector) tail -f /var/log/detector/audit.log
```

### Step 4: Access Dashboard

Open in browser:

```
http://YOUR_SERVER_IP:8080
```

You should see:

- Real-time request rate graph
- Currently banned IPs
- Baseline mean/stddev
- Alert history

### Step 5: Optional — HTTPS with Nginx Reverse Proxy

If deploying publicly, add SSL:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --standalone -d your.domain.com
```

Update `nginx/nginx.conf` to redirect HTTP → HTTPS, then reload:

```bash
docker compose exec nginx nginx -s reload
```

### Troubleshooting

**No IPs being banned?**

- Check `DRY_RUN` is `false` in `.env`
- Verify detector has host network: `docker inspect $(docker compose ps -q detector) | grep -i network`

**Dashboard shows no data?**

- Nginx must be logging; check `hng-access.log` exists
- Detector must have read permissions on shared volume

**Slack alerts not arriving?**

- Verify webhook URL in `.env`
- Check detector logs: `docker logs detector | grep Slack`

---

## Quick Start (Minimal)

For rapid development on a local Linux machine:

```bash
# 1. Clone and enter
git clone https://github.com/yourusername/HNG-STAGE-3.git && cd HNG-STAGE-3

# 2. Configure
cp .env.example .env
sed -i 's/SLACK_WEBHOOK=/SLACK_WEBHOOK=https:\/\/your-webhook/' .env

# 3. Deploy
docker compose up -d --build

# 4. View dashboard
# Open http://localhost:8080
```

### Sample JSON Access Log

Each Nginx log line is a complete JSON object:

```json
{
  "source_ip": "1.2.3.4",
  "timestamp": "2024-01-01T12:00:00+00:00",
  "method": "GET",
  "path": "/",
  "status": 200,
  "response_size": 1234,
  "user_agent": "Mozilla/5.0...",
  "request_time": 0.001
}
```

---

## Detection Logic

| Signal                 | Threshold                | Action                    |
| ---------------------- | ------------------------ | ------------------------- |
| Per-IP z-score         | ≥ 3.0                    | Ban IP                    |
| Per-IP rate multiplier | ≥ 5× baseline            | Ban IP                    |
| Error surge (per IP)   | ≥ 3× baseline error rate | Tighten thresholds by 30% |
| Global z-score or rate | ≥ thresholds             | Slack alert only (no ban) |

### Ban schedule (progressive backoff)

| Offence | Duration   |
| ------- | ---------- |
| 1st     | 10 minutes |
| 2nd     | 30 minutes |
| 3rd     | 2 hours    |
| 4th+    | Permanent  |

---

## Services

| Service   | Port | Notes                                    |
| --------- | ---- | ---------------------------------------- |
| Nginx     | 80   | Reverse proxy, writes JSON access logs   |
| Nextcloud | —    | Internal only                            |
| MariaDB   | —    | Internal only                            |
| Detector  | 8080 | Dashboard + host networking for iptables |

---

## Volume Wiring

```
HNG-nginx-logs
  nginx     → writes  /var/log/nginx/
  nextcloud → reads   /var/log/nginx/ (ro)
  detector  → reads   /var/log/nginx/ (ro)
```

---

## Slack Alerts

The notifier sends three alert types:

- 🚨 **IP BANNED** — includes IP, condition, rate vs baseline, duration
- ✅ **IP UNBANNED** — includes ban count and next ban duration
- ⚠️ **GLOBAL TRAFFIC ANOMALY** — global rate surge alert

---

## Audit Log

Structured log at `/var/log/detector/audit.log`:

```
[2024-01-01T12:00:00Z] BAN ip=1.2.3.4 | condition=z=4.21 | rate=12.500 | baseline=2.100 | duration=600s
[2024-01-01T12:10:00Z] UNBAN ip=1.2.3.4 | ban_count=1 | next_duration=1800s
[2024-01-01T12:01:00Z] BASELINE_RECALC mean=2.1000 | stddev=0.8000 | points=1800
```
