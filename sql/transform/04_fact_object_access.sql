-- fact_object_access for one day (${day}): replace the whole partition.
-- A failed query counts as usage only if it read data. system / information_schema objects are left out.
DELETE FROM iceberg.core.fact_object_access WHERE query_date = DATE '${day}';

INSERT INTO iceberg.core.fact_object_access
WITH q AS (
    SELECT *
    FROM iceberg.raw.query_events e
    WHERE e.create_time >= TIMESTAMP '${day} 00:00:00 UTC'
      AND e.create_time < TIMESTAMP '${day} 00:00:00 UTC' + INTERVAL '1' DAY
      AND (e.query_state = 'FINISHED' OR e.physical_input_bytes > 0)
),
bytes_read AS (
    SELECT q.query_id, i.catalog_name, i.schema_name, i.table_name, sum(i.physical_input_bytes) AS physical_input_bytes
    FROM q
    CROSS JOIN UNNEST(q.inputs) AS i
    GROUP BY 1, 2, 3, 4
),
accesses AS (
    -- reads: every referenced object, the view as well as the table behind it
    SELECT q.query_id, q.user_name, r.catalog_name, r.schema_name, r.table_name,
           'READ' AS access_type, r.directly_referenced AS is_direct, r.columns AS columns_read,
           coalesce(b.physical_input_bytes, 0) AS physical_input_bytes, 0 AS written_bytes
    FROM q
    CROSS JOIN UNNEST(q.referenced_tables) AS r
    LEFT JOIN bytes_read b
      ON b.query_id = q.query_id
     AND b.catalog_name = r.catalog_name AND b.schema_name = r.schema_name AND b.table_name = r.table_name
    UNION ALL
    SELECT q.query_id, q.user_name, q.output.catalog_name, q.output.schema_name, q.output.table_name,
           'WRITE', true, CAST(NULL AS array(varchar)),
           0, coalesce(q.written_bytes, 0)
    FROM q
    WHERE q.output IS NOT NULL
)
SELECT
    a.query_id,
    DATE '${day}',
    u.user_key,
    o.object_key,
    a.access_type,
    a.is_direct,
    a.columns_read,
    a.physical_input_bytes,
    a.written_bytes
FROM accesses a
LEFT JOIN iceberg.core.dim_user u
  ON u.user_login = a.user_name
 AND DATE '${day}' >= u.valid_from
 AND DATE '${day}' < u.valid_to
LEFT JOIN iceberg.core.dim_object o
  ON o.table_catalog = a.catalog_name AND o.table_schema = a.schema_name AND o.table_name = a.table_name
WHERE a.catalog_name <> 'system' AND a.schema_name <> 'information_schema'
