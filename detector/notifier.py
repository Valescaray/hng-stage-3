import json
import time
import urllib.request
import urllib.error

class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _send(self, payload: dict):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except urllib.error.URLError as e:
            print(f"[notifier] Slack error: {e}")
            return False

    def send_ban(self, ip: str, condition: str, rate: float,
                 baseline: float, duration: int):
        duration_str = "permanent" if duration < 0 else f"{duration}s"
        self._send({
            "text": (
                f":rotating_light: *IP BANNED*\n"
                f"IP: `{ip}`\n"
                f"Condition: {condition}\n"
                f"Rate: {rate:.2f} req/s | Baseline: {baseline:.2f} req/s\n"
                f"Ban duration: {duration_str}\n"
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
            )
        })

    def send_unban(self, ip: str, ban_count: int, next_duration: int):
        next_str = "permanent if banned again" if next_duration < 0 else f"{next_duration}s"
        self._send({
            "text": (
                f":white_check_mark: *IP UNBANNED*\n"
                f"IP: `{ip}`\n"
                f"This was ban #{ban_count}\n"
                f"Next ban duration: {next_str}\n"
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
            )
        })

    def send_global_alert(self, condition: str, rate: float, baseline: float):
        self._send({
            "text": (
                f":warning: *GLOBAL TRAFFIC ANOMALY*\n"
                f"Condition: {condition}\n"
                f"Global rate: {rate:.2f} req/s | Baseline: {baseline:.2f} req/s\n"
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
            )
        })
