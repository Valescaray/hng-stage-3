import re
import sys
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# Allow passing log path as argument, default to the VPS path
LOG_PATH = sys.argv[1] if len(sys.argv) > 1 else '/var/log/detector/audit.log'
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else 'screenshots/Baseline-graph.png'

print(f"Reading from: {LOG_PATH}")
print(f"Saving to:    {OUT_PATH}")

timestamps = []
means = []
stddevs = []
hours_seen = set()

if not os.path.exists(LOG_PATH):
    print(f"ERROR: Log file not found at {LOG_PATH}")
    print("If testing locally, pass a sample log path:")
    print("  python3 scripts/plot_baseline.py sample_audit.log screenshots/test.png")
    sys.exit(1)

with open(LOG_PATH) as f:
    for line in f:
        if 'BASELINE_RECALC' not in line:
            continue
        ts_match = re.search(r'\[(.+?)\]', line)
        mean_match = re.search(r'mean=([\d.]+)', line)
        std_match = re.search(r'stddev=([\d.]+)', line)
        if not ts_match or not mean_match:
            continue
        try:
            dt = datetime.strptime(ts_match.group(1), '%Y-%m-%dT%H:%M:%SZ')
            mean = float(mean_match.group(1))
            std = float(std_match.group(1)) if std_match else 0.0
            timestamps.append(dt)
            means.append(mean)
            stddevs.append(std)
            hours_seen.add(dt.hour)
        except ValueError:
            continue

if not timestamps:
    print("ERROR: No BASELINE_RECALC entries found in log.")
    print("Make sure the detector has been running for at least 60 seconds.")
    sys.exit(1)

print(f"Found {len(timestamps)} baseline recalculation entries")
print(f"Hours with data: {sorted(hours_seen)}")

if len(hours_seen) < 2:
    print(f"WARNING: Only {len(hours_seen)} hour slot found.")
    print("Need at least 2 hours of data for a passing Baseline-graph.")
    print("Generating graph anyway — run again after more data accumulates.")
else:
    print(f"READY: {len(hours_seen)} hourly slots found — graph will pass grading.")

# --- Plot ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
fig.suptitle('Detector baseline over time — hourly slots', fontsize=14)

# Shade hourly bands
hour_colors = ['#fff3cd', '#d1ecf1', '#d4edda', '#f8d7da', '#e2d9f3', '#fde2d8']
unique_hours = sorted(hours_seen)
for i, hour in enumerate(unique_hours):
    hour_ts = [t for t in timestamps if t.hour == hour]
    if hour_ts:
        ax1.axvspan(min(hour_ts), max(hour_ts),
                    alpha=0.25,
                    color=hour_colors[i % len(hour_colors)],
                    label=f'Hour {hour:02d}:00')
        ax2.axvspan(min(hour_ts), max(hour_ts),
                    alpha=0.25,
                    color=hour_colors[i % len(hour_colors)])

# Mean plot
ax1.plot(timestamps, means, linewidth=1.5, color='steelblue', marker='o',
         markersize=2, label='effective_mean')
ax1.set_ylabel('Baseline mean (req/s)')
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)

# Annotate the mean value at the start of each hour
for i, hour in enumerate(unique_hours):
    hour_data = [(t, m) for t, m in zip(timestamps, means) if t.hour == hour]
    if hour_data:
        first_t, first_m = hour_data[0]
        ax1.annotate(f'{first_m:.3f}',
                     xy=(first_t, first_m),
                     xytext=(8, 8), textcoords='offset points',
                     fontsize=8, color='steelblue',
                     arrowprops=dict(arrowstyle='->', color='steelblue', lw=0.8))

# Stddev plot
ax2.plot(timestamps, stddevs, linewidth=1.5, color='coral', marker='o',
         markersize=2, label='effective_stddev')
ax2.set_ylabel('Baseline stddev (req/s)')
ax2.set_xlabel('Time')
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)

ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax2.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
plt.xticks(rotation=45)

plt.tight_layout()
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight')
print(f"Saved: {OUT_PATH}")
