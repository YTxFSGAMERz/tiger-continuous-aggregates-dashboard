"""
Tiger Cloud / TimescaleDB Continuous Aggregates Benchmark
Measures Database Engine Execution Time and End-to-End Latency
"""

import os
import json
import time
import psycopg2
import matplotlib.pyplot as plt

from dotenv import load_dotenv
load_dotenv()

DB_URL = os.environ.get("TIMESCALE_SERVICE_URL")
if not DB_URL:
    raise ValueError("TIMESCALE_SERVICE_URL is not set. Please provide it in .env or environment.")



def run_benchmarks():
    print("=" * 75)
    print("      TIGER CLOUD - CONTINUOUS AGGREGATES ENGINE BENCHMARK")
    print("=" * 75)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM device_metrics;")
    total_raw_rows = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM device_metrics_hourly;")
    total_cagg_rows = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM device_metrics_daily;")
    total_daily_cagg_rows = cur.fetchone()[0]

    print(f"\n[Dataset Statistics]")
    print(f" • Raw Hypertable Points:        {total_raw_rows:,}")
    print(f" • Hourly Materialized (CAGG):   {total_cagg_rows:,}")
    print(f" • Daily Rollup (Hierarchical):  {total_daily_cagg_rows:,}")
    print(f" • Row Scan Reduction Factor:   {total_raw_rows / total_cagg_rows:.1f}x\n")

    raw_query = """
    SELECT
        time_bucket('1 hour', time) AS bucket,
        device_id,
        AVG(cpu_usage) AS avg_cpu,
        MAX(cpu_usage) AS max_cpu,
        MIN(cpu_usage) AS min_cpu,
        AVG(memory_usage) AS avg_memory,
        AVG(temperature) AS avg_temp,
        SUM(power_watts) AS total_power
    FROM device_metrics
    WHERE time >= NOW() - INTERVAL '7 days'
    GROUP BY bucket, device_id
    ORDER BY bucket DESC;
    """

    cagg_query = """
    SELECT
        bucket,
        device_id,
        avg_cpu,
        max_cpu,
        min_cpu,
        avg_memory,
        avg_temperature,
        total_power
    FROM device_metrics_hourly
    WHERE bucket >= NOW() - INTERVAL '7 days'
    ORDER BY bucket DESC;
    """

    daily_cagg_query = """
    SELECT
        day_bucket,
        device_id,
        daily_avg_cpu,
        daily_max_cpu,
        daily_avg_temp,
        daily_total_power
    FROM device_metrics_daily
    ORDER BY day_bucket DESC;
    """

    def get_engine_exec_time(sql):
        cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}")
        plan = cur.fetchone()[0][0]
        return plan["Execution Time"], plan["Planning Time"]

    # Warm-up
    get_engine_exec_time(raw_query)
    get_engine_exec_time(cagg_query)
    get_engine_exec_time(daily_cagg_query)

    # Measure 5 runs
    raw_exec_times = []
    cagg_exec_times = []
    daily_exec_times = []

    for _ in range(5):
        raw_exec_times.append(get_engine_exec_time(raw_query)[0])
        cagg_exec_times.append(get_engine_exec_time(cagg_query)[0])
        daily_exec_times.append(get_engine_exec_time(daily_cagg_query)[0])

    avg_raw = sum(raw_exec_times) / len(raw_exec_times)
    avg_cagg = sum(cagg_exec_times) / len(cagg_exec_times)
    avg_daily = sum(daily_exec_times) / len(daily_exec_times)

    speedup_hourly = avg_raw / avg_cagg
    reduction_pct = (1.0 - (avg_cagg / avg_raw)) * 100

    print("-" * 75)
    print(f"{'Query Target':<32} | {'Server Execution Time':<24} | {'Speedup':<10}")
    print("-" * 75)
    print(f"{'Raw Hypertable (100k+ rows)':<32} | {avg_raw:>18.3f} ms | {'1.0x (baseline)':<10}")
    print(f"{'Hourly Continuous Aggregate':<32} | {avg_cagg:>18.3f} ms | {f'{speedup_hourly:.1f}x faster':<10}")
    print(f"{'Daily Hierarchical CAGG':<32} | {avg_daily:>18.3f} ms | {f'{avg_raw / avg_daily:.1f}x faster':<10}")
    print("-" * 75)
    print(f"\n🚀 Continuous Aggregates deliver a {speedup_hourly:.1f}x SPEEDUP ({reduction_pct:.1f}% DB computational reduction)!\n")

    # Generate benchmark plot
    plt.figure(figsize=(9, 5))
    categories = ['Raw Hypertable\n(Compute on Read)', 'Hourly CAGG\n(Pre-computed)', 'Daily Hierarchical\n(Pre-computed)']
    times = [avg_raw, avg_cagg, avg_daily]
    colors = ['#EF4444', '#10B981', '#3B82F6']

    bars = plt.bar(categories, times, color=colors, width=0.5)
    plt.ylabel('Database Execution Time (ms)', fontsize=12, fontweight='bold')
    plt.title('Tiger Cloud / TimescaleDB: Continuous Aggregates Query Acceleration', fontsize=13, fontweight='bold', pad=15)
    plt.yscale('log')
    plt.grid(axis='y', linestyle='--', alpha=0.5)

    for bar, t in zip(bars, times):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, height * 1.15,
                 f'{t:.3f} ms', ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.tight_layout()
    chart_path = os.path.join(os.path.dirname(__file__), 'benchmark_results.png')
    plt.savefig(chart_path, dpi=200)
    plt.close()
    print(f"📊 Benchmark chart saved to: {chart_path}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    run_benchmarks()
