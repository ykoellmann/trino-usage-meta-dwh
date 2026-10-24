-- Question A over time: distinct users per table and week.
-- Distinct counts cannot be summed from days to weeks, so the user stays in the aggregate and is counted again here.

SELECT
    date_trunc('week', a.query_date) AS week,
    o.table_schema,
    o.table_name,
    count(DISTINCT u.user_login) AS distinct_users,
    sum(a.query_count) AS queries
FROM iceberg.mart.agg_object_user_daily a
JOIN iceberg.core.dim_user u ON u.user_key = a.user_key
JOIN iceberg.core.dim_object o ON o.object_key = a.object_key
WHERE a.access_type = 'READ'
  AND o.table_catalog = 'iceberg'
GROUP BY 1, 2, 3
ORDER BY 3, 1
