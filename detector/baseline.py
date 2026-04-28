import time
import math
from collections import deque

class BaselineTracker:
    """
    Maintains a 30-minute rolling window of per-second request counts.
    Recalculates mean and stddev every 60 seconds.
    Keeps per-hour slots and prefers the current hour when it has enough data.
    """

    def __init__(self, config):
        self.window_minutes = config['baseline_window_minutes']
        self.recalc_interval = config['baseline_recalc_interval_seconds']
        self.min_points = config['min_data_points']
        # Floor applied only after real baseline is computed from traffic
        self.floor = config['baseline_mean_floor']

        # Rolling 30-min bucket: one count per second slot
        maxlen = self.window_minutes * 60
        self.per_second_counts = deque(maxlen=maxlen)

        # Per-hour slots: key = hour (0-23), value = list of per-second counts
        self.hourly_slots = {}

        self.effective_mean = self.floor
        self.effective_stddev = 0.0
        self.last_recalc = 0.0

        # Error rate tracking (separate baseline)
        self.error_counts = deque(maxlen=maxlen)
        self.error_mean = 0.0
        self.error_stddev = 0.0

        # For per-second accumulation
        self._current_second = int(time.time())
        self._current_count = 0
        self._current_errors = 0

    def record_request(self, is_error: bool = False):
        now_sec = int(time.time())
        if now_sec != self._current_second:
            # Flush the completed second
            self.per_second_counts.append(self._current_count)
            self.error_counts.append(self._current_errors)

            # Store into hourly slot
            hour = time.localtime(self._current_second).tm_hour
            self.hourly_slots.setdefault(hour, deque(maxlen=3600))
            self.hourly_slots[hour].append(self._current_count)

            self._current_second = now_sec
            self._current_count = 0
            self._current_errors = 0

        self._current_count += 1
        if is_error:
            self._current_errors += 1

    def maybe_recalculate(self) -> bool:
        """Call frequently; recalculates every recalc_interval seconds. Returns True if recalculated."""
        now = time.time()
        if now - self.last_recalc < self.recalc_interval:
            return False

        self.last_recalc = now
        current_hour = time.localtime().tm_hour
        hour_data = self.hourly_slots.get(current_hour, deque())

        # Use current-hour data if it has enough points, else use rolling window
        if len(hour_data) >= self.min_points:
            data = list(hour_data)
        elif len(self.per_second_counts) >= self.min_points:
            data = list(self.per_second_counts)
        else:
            return False  # Not enough data yet

        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        stddev = math.sqrt(variance)

        self.effective_mean = max(mean, self.floor)
        self.effective_stddev = stddev

        # Recalculate error baseline
        if len(self.error_counts) >= self.min_points:
            err_data = list(self.error_counts)
            err_mean = sum(err_data) / len(err_data)
            err_variance = sum((x - err_mean) ** 2 for x in err_data) / len(err_data)
            self.error_mean = max(err_mean, 0.01)
            self.error_stddev = math.sqrt(err_variance)

        return True

    def get_z_score(self, current_rate: float) -> float:
        if self.effective_stddev == 0:
            return 0.0
        return (current_rate - self.effective_mean) / self.effective_stddev

    def get_rate_multiplier(self, current_rate: float) -> float:
        if self.effective_mean == 0:
            return 0.0
        return current_rate / self.effective_mean
