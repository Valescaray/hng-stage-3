import time
import os

class AuditLogger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def _write(self, line: str):
        with open(self.path, 'a') as f:
            f.write(line + '\n')
        print(line)  # also print to stdout for docker logs

    def log_ban(self, ip: str, condition: str, rate: float,
                baseline: float, duration: int):
        dur = "permanent" if duration < 0 else f"{duration}s"
        self._write(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
            f"BAN ip={ip} | condition={condition} | "
            f"rate={rate:.3f} | baseline={baseline:.3f} | duration={dur}"
        )

    def log_unban(self, ip: str, count: int, next_duration: int):
        dur = "permanent" if next_duration < 0 else f"{next_duration}s"
        self._write(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
            f"UNBAN ip={ip} | ban_count={count} | next_duration={dur}"
        )

    def log_baseline_recalc(self, mean: float, stddev: float, data_points: int):
        self._write(
            f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] "
            f"BASELINE_RECALC mean={mean:.4f} | stddev={stddev:.4f} | "
            f"points={data_points}"
        )
