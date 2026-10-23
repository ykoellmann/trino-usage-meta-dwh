-- agg_user_resources_daily for one day (${day}): replace the whole partition.
DELETE FROM iceberg.mart.agg_user_resources_daily WHERE query_date = DATE '${day}';

INSERT INTO iceberg.mart.agg_user_resources_daily
SELECT
    query_date,
    user_key,
    count(*),
    sum(cpu_time_ms),
    sum(cumulative_memory),
    sum(physical_input_bytes),
    sum(queued_time_ms),
    max(peak_user_memory_bytes)
FROM iceberg.core.fact_query
WHERE query_date = DATE '${day}'
GROUP BY query_date, user_key
