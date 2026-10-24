-- Tables that are written to but never read in a period. They cost storage and compute and benefit nobody.
WITH p AS (
    SELECT DATE '2026-10-12' AS from_day, DATE '2026-10-22' AS to_day
)
SELECT
    o.table_schema,
    o.table_name,
    sum(a.query_count) AS write_queries,
    sum(a.written_bytes) AS written_bytes
FROM iceberg.mart.agg_object_user_daily a
JOIN iceberg.core.dim_object o ON o.object_key = a.object_key
CROSS JOIN p
WHERE a.access_type = 'WRITE'
  AND a.query_date BETWEEN p.from_day AND p.to_day
  AND o.table_catalog = 'iceberg'
  AND NOT EXISTS (
      SELECT 1
      FROM iceberg.mart.agg_object_user_daily r
      WHERE r.object_key = a.object_key
        AND r.access_type = 'READ'
        AND r.query_date BETWEEN p.from_day AND p.to_day
  )
GROUP BY 1, 2
ORDER BY 4 DESC
