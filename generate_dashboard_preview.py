import os
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from dotenv import load_dotenv
load_dotenv()

DB_URL = os.environ.get("TIMESCALE_SERVICE_URL")
if not DB_URL:
    raise ValueError("TIMESCALE_SERVICE_URL is not set.")


conn = psycopg2.connect(DB_URL)

query = """
SELECT bucket, device_id, avg_cpu, max_cpu, min_cpu, avg_memory, avg_temperature, total_power
FROM device_metrics_hourly
WHERE bucket >= NOW() - INTERVAL '7 days'
ORDER BY bucket ASC;
"""
df = pd.read_sql_query(query, conn)
conn.close()

plt.style.use('dark_background')
fig = plt.figure(figsize=(16, 10), facecolor='#0E1117')

# Layout
gs = fig.add_gridspec(3, 2, height_ratios=[0.3, 1, 1], hspace=0.35, wspace=0.25)

# Banner / Header
ax_header = fig.add_subplot(gs[0, :])
ax_header.axis('off')
ax_header.text(0.0, 0.75, "⚡ Edge Fleet Real-Time Telemetry Dashboard", fontsize=20, fontweight='bold', color='#FFFFFF')
ax_header.text(0.0, 0.40, "Accelerated by Tiger Cloud (TimescaleDB) Continuous Aggregates (CAGGs)", fontsize=13, color='#9CA3AF')

kpi_text = "Ingested Points: 100,805   |   Hourly CAGG Materialized: 1,685   |   Scan Reduction: 59.8x   |   Latency Speedup: 50.1x (0.52 ms)"
ax_header.text(0.0, 0.05, kpi_text, fontsize=11, fontweight='semibold', color='#10B981',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='#1F2937', edgecolor='#374151'))

devices = df['device_id'].unique()
palette = ['#38BDF8', '#818CF8', '#F472B6', '#34D399', '#FBBF24']

# Subplot 1: CPU Utilization
ax1 = fig.add_subplot(gs[1, 0])
ax1.set_facecolor('#111827')
for i, dev in enumerate(devices):
    sub = df[df['device_id'] == dev]
    ax1.plot(sub['bucket'], sub['avg_cpu'], label=dev, color=palette[i % len(palette)], linewidth=1.8)
ax1.set_title("Hourly Average CPU Utilization (%)", fontsize=12, fontweight='bold', color='#E5E7EB', pad=10)
ax1.set_ylabel("Avg CPU %", fontsize=10, color='#9CA3AF')
ax1.grid(True, linestyle='--', alpha=0.2)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
ax1.legend(loc='upper right', framealpha=0.3, fontsize=8)

# Subplot 2: Temperature
ax2 = fig.add_subplot(gs[1, 1])
ax2.set_facecolor('#111827')
for i, dev in enumerate(devices):
    sub = df[df['device_id'] == dev]
    ax2.plot(sub['bucket'], sub['avg_temperature'], label=dev, color=palette[i % len(palette)], linewidth=1.8)
ax2.set_title("Hourly Average Core Temperature (°C)", fontsize=12, fontweight='bold', color='#E5E7EB', pad=10)
ax2.set_ylabel("Temp (°C)", fontsize=10, color='#9CA3AF')
ax2.grid(True, linestyle='--', alpha=0.2)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))

# Subplot 3: Memory Usage
ax3 = fig.add_subplot(gs[2, 0])
ax3.set_facecolor('#111827')
for i, dev in enumerate(devices):
    sub = df[df['device_id'] == dev]
    ax3.plot(sub['bucket'], sub['avg_memory'], label=dev, color=palette[i % len(palette)], linewidth=1.8)
ax3.set_title("Hourly Average Memory Usage (%)", fontsize=12, fontweight='bold', color='#E5E7EB', pad=10)
ax3.set_ylabel("Memory %", fontsize=10, color='#9CA3AF')
ax3.grid(True, linestyle='--', alpha=0.2)
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))

# Subplot 4: Query Latency Benchmark Comparison
ax4 = fig.add_subplot(gs[2, 1])
ax4.set_facecolor('#111827')
categories = ['Raw Hypertable\n(Compute on Read)', 'Continuous Aggregate\n(Pre-computed CAGG)', 'Daily Hierarchical\n(Pre-computed Rollup)']
latencies = [26.287, 0.525, 0.055]
bar_colors = ['#EF4444', '#10B981', '#3B82F6']
bars = ax4.bar(categories, latencies, color=bar_colors, width=0.45)
ax4.set_yscale('log')
ax4.set_title("Server Engine Query Execution Time (ms) - Log Scale", fontsize=12, fontweight='bold', color='#E5E7EB', pad=10)
ax4.set_ylabel("Execution Time (ms)", fontsize=10, color='#9CA3AF')
ax4.grid(True, axis='y', linestyle='--', alpha=0.2)

for bar, val in zip(bars, latencies):
    ax4.text(bar.get_x() + bar.get_width()/2.0, val * 1.3, f"{val:.3f} ms",
             ha='center', va='bottom', fontsize=10, fontweight='bold', color='#FFFFFF')

output_path = os.path.join(os.path.dirname(__file__), "dashboard_screenshot.png")
plt.savefig(output_path, dpi=200, bbox_inches='tight')
plt.close()
print(f"✅ Dashboard screenshot generated at: {output_path}")
