-- agg_object_user_daily for one day (${day}): replace the whole partition.
DELETE FROM iceberg.mart.agg_object_user_daily WHERE query_date = DATE '${day}';

INSERT INTO iceberg.mart.agg_object_user_daily
SELECT
    query_date,
    object_key,
    user_key,
    access_type,
    is_direct,
    count(DISTINCT query_id),
    sum(physical_input_bytes),
    sum(written_bytes)
FROM iceberg.core.fact_object_access
WHERE query_date = DATE '${day}'
GROUP BY 1, 2, 3, 4, 5
