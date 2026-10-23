-- Question B: how many resources did each team consume in a period?
-- Change the period in the first line. Add a WHERE on team_name for a single team.
-- The team is the one the user had when the query ran (SCD 2 on dim_user).
-- Failed queries count, they used resources. Service accounts count with the team that runs them.
-- Units: cpu in hours, memory in GB-hours (cumulative_memory is byte-seconds), data in GB (10^9 bytes).
WITH p AS (
    SELECT DATE '2026-10-19' AS from_day, DATE '2026-10-22' AS to_day
)
SELECT
    u.team_id,
    u.team_name,
    sum(a.query_count) AS queries,
    round(sum(a.cpu_time_ms) / 3600000e0, 3) AS cpu_hours,
    round(sum(a.cumulative_memory) / 1e9 / 3600, 3) AS memory_gb_hours,
    round(sum(a.physical_input_bytes) / 1e9, 3) AS data_read_gb,
    round(max(a.max_peak_user_memory_bytes) / 1e9, 3) AS largest_query_peak_memory_gb,
    round(sum(a.queued_time_ms) / 1000e0, 1) AS queued_seconds
FROM iceberg.mart.agg_user_resources_daily a
JOIN iceberg.core.dim_user u ON u.user_key = a.user_key
CROSS JOIN p
WHERE a.query_date BETWEEN p.from_day AND p.to_day
GROUP BY u.team_id, u.team_name
ORDER BY cpu_hours DESC
