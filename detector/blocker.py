import subprocess
import time

class Blocker:
    """Manages iptables DROP rules for banned IPs.

    When dry_run=True every iptables call is replaced by a log message.
    In-memory state (self.banned) is updated identically in both modes so
    the dashboard, audit log, and unban schedule all work normally.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.banned: dict = {}  # ip -> {banned_at, ban_index, duration}

    def ban(self, ip: str, duration_seconds: int):
        if ip in self.banned:
            return  # Already banned

        if self.dry_run:
            print(f"[blocker] DRY_RUN — would ban {ip} for {duration_seconds}s")
        else:
            try:
                subprocess.run(
                    ['iptables', '-I', 'INPUT', '-s', ip, '-j', 'DROP'],
                    check=True, capture_output=True
                )
            except subprocess.CalledProcessError as e:
                print(f"[blocker] iptables error banning {ip}: {e.stderr}")
                return  # Don't record as banned if the rule failed

        # Update in-memory state regardless of dry_run
        self.banned[ip] = {
            'banned_at': time.time(),
            'ban_index': 0,
            'duration': duration_seconds,
        }

    def unban(self, ip: str):
        if self.dry_run:
            print(f"[blocker] DRY_RUN — would unban {ip}")
        else:
            try:
                subprocess.run(
                    ['iptables', '-D', 'INPUT', '-s', ip, '-j', 'DROP'],
                    check=True, capture_output=True
                )
            except subprocess.CalledProcessError:
                pass  # Rule may already be gone; always clean up memory

        self.banned.pop(ip, None)

    def is_banned(self, ip: str) -> bool:
        return ip in self.banned
