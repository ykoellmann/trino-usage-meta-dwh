-- Tables that nobody read or wrote in a period.
-- Tables first seen after the start of the period are skipped, they had less than the full period to be used.
-- Deleted tables are skipped as well.
WITH p AS (
    SELECT DATE '2026-10-19' AS from_day, DATE '2026-10-22' AS to_day
)
SELECT o.table_schema, o.table_name, o.table_type, o.first_seen
FROM iceberg.core.dim_object o
CROSS JOIN p
WHERE o.table_catalog = 'iceberg'
  AND o.in_directory
  AND o.deleted_at IS NULL
  AND o.first_seen <= p.from_day
  AND NOT EXISTS (
      SELECT 1
      FROM iceberg.mart.agg_object_user_daily a
      WHERE a.object_key = o.object_key
        AND a.query_date BETWEEN p.from_day AND p.to_day
  )
ORDER BY o.table_schema, o.table_name
