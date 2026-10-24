-- Question A: how many distinct users queried table X in a period?
-- Change the period and, optionally, the table in the first line. table_name = NULL lists all tables.
-- Distinct users are counted by login, never by user_key: a user with a team change has two keys.
-- Reads only. A view and the table behind it both count as used. Service accounts are users like any other,
-- human_users shows the number without them.
WITH p AS (
    SELECT DATE '2026-10-12' AS from_day, DATE '2026-10-22' AS to_day, CAST('ide_events' AS varchar) AS table_name
)
SELECT
    o.table_schema,
    o.table_name,
    count(DISTINCT u.user_login) AS distinct_users,
    count(DISTINCT IF(u.account_type = 'human', u.user_login)) AS human_users,
    sum(a.query_count) AS queries
FROM iceberg.mart.agg_object_user_daily a
JOIN iceberg.core.dim_user u ON u.user_key = a.user_key
JOIN iceberg.core.dim_object o ON o.object_key = a.object_key
CROSS JOIN p
WHERE a.access_type = 'READ'
  AND a.query_date BETWEEN p.from_day AND p.to_day
  AND o.table_catalog = 'iceberg'
  AND (p.table_name IS NULL OR o.table_name = p.table_name)
GROUP BY 1, 2
ORDER BY 3 DESC, 2
