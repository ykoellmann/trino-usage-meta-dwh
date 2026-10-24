-- Question B over time: resources per team and week.
-- Everything here is a sum, except the peak memory, which is a maximum. Both can be combined over any period.
SELECT
    date_trunc('week', a.query_date) AS week,
    u.team_name,
    sum(a.query_count) AS queries,
    round(sum(a.cpu_time_ms) / 3600000e0, 3) AS cpu_hours,
    round(sum(a.physical_input_bytes) / 1e9, 3) AS data_read_gb,
    round(max(a.max_peak_user_memory_bytes) / 1e9, 3) AS largest_query_peak_memory_gb
FROM iceberg.mart.agg_user_resources_daily a
JOIN iceberg.core.dim_user u ON u.user_key = a.user_key
GROUP BY 1, 2
ORDER BY 2, 1
