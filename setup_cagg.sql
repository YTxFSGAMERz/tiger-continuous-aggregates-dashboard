-- Tiger Cloud / TimescaleDB Continuous Aggregates Setup Script
-- Challenge: Accelerate Dashboards with Continuous Aggregates (Global Hack Week)

-- Drop existing views and tables if present
DROP MATERIALIZED VIEW IF EXISTS device_metrics_daily CASCADE;
DROP MATERIALIZED VIEW IF EXISTS device_metrics_hourly CASCADE;
DROP TABLE IF EXISTS device_metrics CASCADE;

-- 1. Create base time-series table
CREATE TABLE device_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id TEXT NOT NULL,
    cpu_usage DOUBLE PRECISION NOT NULL,
    memory_usage DOUBLE PRECISION NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    power_watts DOUBLE PRECISION NOT NULL
);

-- 2. Convert to TimescaleDB Hypertable
SELECT create_hypertable('device_metrics', 'time', chunk_time_interval => INTERVAL '1 day');

-- 3. Create composite index for device and time lookups
CREATE INDEX idx_device_metrics_device_time ON device_metrics (device_id, time DESC);

-- 4. Seed realistic time-series dataset
-- 5 edge nodes, 1 reading every minute for 14 days (~100,800 data points)
INSERT INTO device_metrics (time, device_id, cpu_usage, memory_usage, temperature, power_watts)
SELECT
    t AS time,
    d.device_id,
    ROUND((20 + 55 * random() + 15 * sin(EXTRACT(EPOCH FROM t) / 3600.0))::numeric, 2) AS cpu_usage,
    ROUND((40 + 35 * random() + 10 * cos(EXTRACT(EPOCH FROM t) / 7200.0))::numeric, 2) AS memory_usage,
    ROUND((35 + 25 * random() + 5 * sin(EXTRACT(EPOCH FROM t) / 1800.0))::numeric, 2) AS temperature,
    ROUND((100 + 120 * random() + 20 * sin(EXTRACT(EPOCH FROM t) / 3600.0))::numeric, 2) AS power_watts
FROM
    generate_series(NOW() - INTERVAL '14 days', NOW(), INTERVAL '1 minute') AS t
CROSS JOIN (
    VALUES
        ('edge-node-01'),
        ('edge-node-02'),
        ('edge-node-03'),
        ('edge-node-04'),
        ('edge-node-05')
) AS d(device_id);

-- 5. Create Continuous Aggregate (CAGG) for Hourly Metrics
CREATE MATERIALIZED VIEW device_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    AVG(cpu_usage) AS avg_cpu,
    MAX(cpu_usage) AS max_cpu,
    MIN(cpu_usage) AS min_cpu,
    AVG(memory_usage) AS avg_memory,
    MAX(memory_usage) AS max_memory,
    AVG(temperature) AS avg_temperature,
    MAX(temperature) AS max_temperature,
    AVG(power_watts) AS avg_power,
    SUM(power_watts) AS total_power,
    COUNT(*) AS sample_count
FROM device_metrics
GROUP BY bucket, device_id
WITH NO DATA;

-- 6. Add Continuous Aggregate Refresh Policy (automated background worker)
SELECT add_continuous_aggregate_policy('device_metrics_hourly',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes');

-- 7. Populate initial continuous aggregate materialized data
CALL refresh_continuous_aggregate('device_metrics_hourly', NULL, NULL);

-- 8. Create Hierarchical Continuous Aggregate for Daily Rollups
CREATE MATERIALIZED VIEW device_metrics_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', bucket) AS day_bucket,
    device_id,
    AVG(avg_cpu) AS daily_avg_cpu,
    MAX(max_cpu) AS daily_max_cpu,
    AVG(avg_temperature) AS daily_avg_temp,
    SUM(total_power) AS daily_total_power,
    SUM(sample_count) AS total_samples
FROM device_metrics_hourly
GROUP BY day_bucket, device_id
WITH NO DATA;

-- 9. Add Continuous Aggregate Refresh Policy for Daily Rollup
SELECT add_continuous_aggregate_policy('device_metrics_daily',
    start_offset => INTERVAL '90 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- 10. Populate Daily continuous aggregate
CALL refresh_continuous_aggregate('device_metrics_daily', NULL, NULL);
