import time
from collections import deque

class AnomalyDetector:
    """
    Tracks per-IP and global request rates using deque-based sliding windows
    over the last 60 seconds. Flags anomalies by z-score or rate multiplier.
    """

    def __init__(self, config, baseline):
        self.window_seconds = config['window_seconds']
        self.z_threshold = config['z_score_threshold']
        self.rate_threshold = config['rate_multiplier_threshold']
        self.error_surge_mult = config['error_surge_multiplier']
        self.baseline = baseline

        # Global sliding window: deque of (timestamp, is_error) tuples
        self.global_window: deque = deque()

        # Per-IP sliding windows: {ip: deque of (timestamp, is_error)}
        self.ip_windows: dict = {}

    def _evict_old(self, window: deque, now: float):
        """Remove entries older than window_seconds from the left of the deque."""
        cutoff = now - self.window_seconds
        while window and window[0][0] < cutoff:
            window.popleft()

    def record(self, ip: str, is_error: bool):
        now = time.time()

        # Global window
        self.global_window.append((now, is_error))
        self._evict_old(self.global_window, now)

        # Per-IP window
        if ip not in self.ip_windows:
            self.ip_windows[ip] = deque()
        self.ip_windows[ip].append((now, is_error))
        self._evict_old(self.ip_windows[ip], now)

    def get_ip_rate(self, ip: str) -> float:
        """Requests per second for ip over the last window_seconds."""
        window = self.ip_windows.get(ip, deque())
        now = time.time()
        self._evict_old(window, now)
        return len(window) / self.window_seconds

    def get_global_rate(self) -> float:
        now = time.time()
        self._evict_old(self.global_window, now)
        return len(self.global_window) / self.window_seconds

    def get_ip_error_rate(self, ip: str) -> float:
        window = self.ip_windows.get(ip, deque())
        now = time.time()
        self._evict_old(window, now)
        errors = sum(1 for _, is_err in window if is_err)
        total = len(window)
        return errors / total if total > 0 else 0.0

    def check_ip(self, ip: str) -> dict | None:
        """Returns anomaly dict if ip is anomalous, else None."""
        rate = self.get_ip_rate(ip)
        z = self.baseline.get_z_score(rate)
        mult = self.baseline.get_rate_multiplier(rate)

        # Tighten thresholds if error rate is surging for this IP
        z_threshold = self.z_threshold
        rate_threshold = self.rate_threshold
        err_rate = self.get_ip_error_rate(ip)
        if (self.baseline.error_mean > 0 and
                err_rate > self.baseline.error_mean * self.error_surge_mult):
            z_threshold *= 0.7
            rate_threshold *= 0.7

        if z >= z_threshold or mult >= rate_threshold:
            return {
                'type': 'ip',
                'ip': ip,
                'rate': rate,
                'z_score': z,
                'multiplier': mult,
                'condition': f'z={z:.2f}' if z >= z_threshold else f'rate={mult:.1f}x baseline',
                'baseline_mean': self.baseline.effective_mean,
                'baseline_stddev': self.baseline.effective_stddev,
            }
        return None

    def check_global(self) -> dict | None:
        """Returns anomaly dict if global traffic is anomalous."""
        rate = self.get_global_rate()
        z = self.baseline.get_z_score(rate)
        mult = self.baseline.get_rate_multiplier(rate)

        if z >= self.z_threshold or mult >= self.rate_threshold:
            return {
                'type': 'global',
                'rate': rate,
                'z_score': z,
                'multiplier': mult,
                'condition': f'z={z:.2f}' if z >= self.z_threshold else f'rate={mult:.1f}x baseline',
                'baseline_mean': self.baseline.effective_mean,
                'baseline_stddev': self.baseline.effective_stddev,
            }
        return None
