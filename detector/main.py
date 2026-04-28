#!/usr/bin/env python3
import os
import time
import yaml
import threading
import psutil
from collections import deque, Counter

from monitor import LogMonitor
from baseline import BaselineTracker
from detector import AnomalyDetector
from blocker import Blocker
from unbanner import Unbanner
from notifier import SlackNotifier
from dashboard import DashboardServer
from audit import AuditLogger


def load_config(path='config.yaml'):
    with open(path) as f:
        cfg = yaml.safe_load(f)

    # Environment variables take precedence over config.yaml values.
    # This lets a single Docker image run in both local (dry_run=true)
    # and production (DRY_RUN=false) without a rebuild.
    cfg['slack_webhook_url'] = os.environ.get(
        'SLACK_WEBHOOK_URL', cfg['slack_webhook_url']
    )
    cfg['dry_run'] = (
        os.environ.get('DRY_RUN', 'false')
        .lower() == 'true'
    )

    return cfg


def main():
    config = load_config()
    start_time = time.time()

    # Shared dashboard state
    state = {
        'global_rps': 0.0,
        'baseline_mean': 0.0,
        'baseline_stddev': 0.0,
        'banned_ips': [],
        'top_ips': [],
        'cpu_pct': 0.0,
        'mem_pct': 0.0,
        'uptime': '0s',
    }

    # Components
    baseline = BaselineTracker(config)
    detector = AnomalyDetector(config, baseline)
    blocker = Blocker(dry_run=config['dry_run'])
    if config['dry_run']:
        print("[main] DRY_RUN mode — iptables calls are suppressed (set DRY_RUN=false for live blocking)")
    else:
        print("[main] LIVE BLOCKING mode — iptables rules will be applied")
    notifier = SlackNotifier(config['slack_webhook_url'])
    audit = AuditLogger(config['audit_log'])
    unbanner = Unbanner(blocker, notifier, audit)

    # Dashboard
    dash = DashboardServer(config['dashboard_host'], config['dashboard_port'], state)
    dash.start()
    print(f"[main] Dashboard running on port {config['dashboard_port']}")

    monitor = LogMonitor(config['log_path'])

    # Recent IPs for top-10 (last 60s)
    recent_ips: deque = deque()

    COOLDOWN = {}   # ip -> last_ban_time (prevent re-ban spam)

    print("[main] Starting log tail...")
    for entry in monitor.tail():
        ip = entry.get('source_ip', '').split(',')[0].strip() or '0.0.0.0'
        status = int(entry.get('status', 200))
        is_error = status >= 400

        baseline.record_request(is_error)
        detector.record(ip, is_error)

        now = time.time()

        # Track recent IPs for top-10
        recent_ips.append((now, ip))
        while recent_ips and recent_ips[0][0] < now - 60:
            recent_ips.popleft()

        # Baseline recalculation
        if baseline.maybe_recalculate():
            audit.log_baseline_recalc(
                baseline.effective_mean,
                baseline.effective_stddev,
                len(baseline.per_second_counts)
            )

        # Unban checks
        unbanner.tick()

        # Anomaly detection — per IP
        if ip != '0.0.0.0' and not blocker.is_banned(ip):
            cooldown_ok = (now - COOLDOWN.get(ip, 0)) > 30
            if cooldown_ok:
                anomaly = detector.check_ip(ip)
                if anomaly:
                    duration = unbanner.next_ban_duration(ip)
                    blocker.ban(ip, duration)
                    COOLDOWN[ip] = now
                    dur_str = "permanent" if duration < 0 else f"{duration}s"
                    notifier.send_ban(
                        ip, anomaly['condition'], anomaly['rate'],
                        anomaly['baseline_mean'], duration
                    )
                    audit.log_ban(
                        ip, anomaly['condition'], anomaly['rate'],
                        anomaly['baseline_mean'], duration
                    )
                    print(f"[main] BANNED {ip}: {anomaly['condition']}, duration={dur_str}")

        # Global anomaly — Slack alert only, no ban
        global_anomaly = detector.check_global()
        if global_anomaly:
            notifier.send_global_alert(
                global_anomaly['condition'],
                global_anomaly['rate'],
                global_anomaly['baseline_mean']
            )

        # Update dashboard state periodically
        elapsed = int(now - start_time)
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        ip_counts = Counter(ip for _, ip in recent_ips)
        state.update({
            'global_rps': detector.get_global_rate(),
            'baseline_mean': baseline.effective_mean,
            'baseline_stddev': baseline.effective_stddev,
            'banned_ips': [
                {'ip': ip,
                 'remaining': max(0, int(info['duration'] - (now - info['banned_at'])))
                              if info['duration'] >= 0 else -1}
                for ip, info in blocker.banned.items()
            ],
            'top_ips': [
                {'ip': k, 'rate': v / 60}
                for k, v in ip_counts.most_common(10)
            ],
            'cpu_pct': psutil.cpu_percent(),
            'mem_pct': psutil.virtual_memory().percent,
            'uptime': f"{h}h {m}m {s}s",
        })


if __name__ == '__main__':
    main()
