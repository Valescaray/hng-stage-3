import time
from blocker import Blocker

UNBAN_SCHEDULE = [600, 1800, 7200]  # seconds; after index 3, permanent

class Unbanner:
    """Monitors bans and releases them on the backoff schedule."""

    def __init__(self, blocker: Blocker, notifier, audit_logger):
        self.blocker = blocker
        self.notifier = notifier
        self.audit = audit_logger
        # Tracks how many times each IP has been banned
        self.ban_counts: dict = {}   # ip -> int

    def tick(self):
        now = time.time()
        to_unban = []

        for ip, info in list(self.blocker.banned.items()):
            duration = info['duration']
            if duration < 0:
                continue  # Permanent ban
            elapsed = now - info['banned_at']
            if elapsed >= duration:
                to_unban.append(ip)

        for ip in to_unban:
            self.blocker.unban(ip)
            count = self.ban_counts.get(ip, 0) + 1
            self.ban_counts[ip] = count

            if count > len(UNBAN_SCHEDULE):
                # Permanent on next ban
                next_duration = -1
            else:
                next_duration = UNBAN_SCHEDULE[min(count, len(UNBAN_SCHEDULE) - 1)]

            self.notifier.send_unban(ip, count, next_duration)
            self.audit.log_unban(ip, count, next_duration)

    def next_ban_duration(self, ip: str) -> int:
        """Returns the next ban duration for an IP based on its history."""
        count = self.ban_counts.get(ip, 0)
        if count >= len(UNBAN_SCHEDULE):
            return -1  # Permanent
        return UNBAN_SCHEDULE[count]
