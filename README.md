# HNG Stage 3 — Anomaly Detector Stack

A Docker Compose stack that deploys **Nextcloud** behind **Nginx**, with a **Python detector daemon** that monitors access logs in real-time, detects traffic anomalies using a statistical baseline, bans offending IPs via `iptables`, and exposes a live dashboard.

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

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose installed
- A Linux host (iptables required for the detector)

### 2. Configure

Edit `detector/config.yaml`:

```yaml
slack_webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

Edit `docker-compose.yml` and set your server IP:

```yaml
NEXTCLOUD_TRUSTED_DOMAINS: "YOUR_SERVER_IP"
```

### 3. Deploy

```bash
docker compose up -d --build
```

### 4. Verify volumes

```bash
docker volume ls | grep HNG-nginx-logs
# Expected: local    HNG-nginx-logs
```

### 5. Check the log

```bash
docker exec $(docker compose ps -q nginx) cat /var/log/nginx/hng-access.log
```

Each line is a JSON object with all required fields:
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

### 6. Dashboard

Open `http://YOUR_SERVER_IP:8080` to see the live anomaly dashboard.

---

## Detection Logic

| Signal | Threshold | Action |
|--------|-----------|--------|
| Per-IP z-score | ≥ 3.0 | Ban IP |
| Per-IP rate multiplier | ≥ 5× baseline | Ban IP |
| Error surge (per IP) | ≥ 3× baseline error rate | Tighten thresholds by 30% |
| Global z-score or rate | ≥ thresholds | Slack alert only (no ban) |

### Ban schedule (progressive backoff)

| Offence | Duration |
|---------|----------|
| 1st | 10 minutes |
| 2nd | 30 minutes |
| 3rd | 2 hours |
| 4th+ | Permanent |

---

## Services

| Service | Port | Notes |
|---------|------|-------|
| Nginx | 80 | Reverse proxy, writes JSON access logs |
| Nextcloud | — | Internal only |
| MariaDB | — | Internal only |
| Detector | 8080 | Dashboard + host networking for iptables |

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
