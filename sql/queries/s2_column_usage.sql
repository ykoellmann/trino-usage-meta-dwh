-- How often each column was read in a period.
-- Unused columns are the ones missing here. To list them, left join this result to the table's column list,
-- for example iceberg.information_schema.columns. That list is not stored in the DWH, and the tables of this
-- test setup are synthetic and have no columns in Trino.
-- Columns read through a view count for the table behind it.
WITH p AS (
    SELECT DATE '2026-10-19' AS from_day, DATE '2026-10-22' AS to_day
)
SELECT
    o.table_schema,
    o.table_name,
    c.column_name,
    count(*) AS reads
FROM iceberg.core.fact_object_access f
CROSS JOIN UNNEST(f.columns_read) AS c(column_name)
JOIN iceberg.core.dim_object o ON o.object_key = f.object_key
CROSS JOIN p
WHERE f.access_type = 'READ'
  AND f.query_date BETWEEN p.from_day AND p.to_day
  AND o.table_catalog = 'iceberg'
GROUP BY o.table_schema, o.table_name, c.column_name
ORDER BY o.table_name, reads DESC, c.column_name
