import time
import json
import os
from collections import deque

class LogMonitor:
    """Continuously tails the nginx access log and yields parsed entries."""

    def __init__(self, log_path):
        self.log_path = log_path

    def tail(self):
        """Generator: yields parsed JSON log lines as dicts, blocking until new lines arrive."""
        # Wait for log file to exist
        while not os.path.exists(self.log_path):
            time.sleep(1)

        with open(self.log_path, 'r') as f:
            # Seek to end on startup so we don't replay old logs
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    yield entry
                except json.JSONDecodeError:
                    continue
