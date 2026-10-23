-- dim_object for one day (${day}). The key is a hash of catalog.schema.table, so it is the same on every run.
--
-- 1. Objects from the directory snapshot: add new ones, complete event-only ones, undelete reappearing ones.
MERGE INTO iceberg.core.dim_object AS t
USING (
    SELECT
        from_big_endian_64(xxhash64(to_utf8(table_catalog || '.' || table_schema || '.' || table_name))) AS object_key,
        table_catalog, table_schema, table_name, table_type
    FROM iceberg.raw.object_snapshot
    WHERE snapshot_date = DATE '${day}'
) AS s
ON t.object_key = s.object_key
WHEN MATCHED AND (
        NOT t.in_directory
        OR t.table_type <> s.table_type
        OR (t.deleted_at IS NOT NULL AND DATE '${day}' > t.deleted_at)
    ) THEN
    UPDATE SET
        table_type = s.table_type,
        in_directory = true,
        deleted_at = IF(t.deleted_at IS NOT NULL AND DATE '${day}' > t.deleted_at, NULL, t.deleted_at)
WHEN NOT MATCHED THEN
    INSERT (object_key, table_catalog, table_schema, table_name, table_type, in_directory, first_seen, deleted_at)
    VALUES (s.object_key, s.table_catalog, s.table_schema, s.table_name, s.table_type, true, DATE '${day}', NULL);

-- 2. Objects that only show up in events (not in the directory): add them, so no usage is lost.
--    Same rule as in fact_object_access: a failed query counts only if it read data.
MERGE INTO iceberg.core.dim_object AS t
USING (
    SELECT DISTINCT
        from_big_endian_64(xxhash64(to_utf8(catalog_name || '.' || schema_name || '.' || table_name))) AS object_key,
        catalog_name, schema_name, table_name
    FROM (
        SELECT r.catalog_name, r.schema_name, r.table_name
        FROM iceberg.raw.query_events e
        CROSS JOIN UNNEST(e.referenced_tables) AS r
        WHERE e.create_time >= TIMESTAMP '${day} 00:00:00 UTC'
          AND e.create_time < TIMESTAMP '${day} 00:00:00 UTC' + INTERVAL '1' DAY
          AND (e.query_state = 'FINISHED' OR e.physical_input_bytes > 0)
        UNION ALL
        SELECT e.output.catalog_name, e.output.schema_name, e.output.table_name
        FROM iceberg.raw.query_events e
        WHERE e.output IS NOT NULL
          AND e.create_time >= TIMESTAMP '${day} 00:00:00 UTC'
          AND e.create_time < TIMESTAMP '${day} 00:00:00 UTC' + INTERVAL '1' DAY
          AND (e.query_state = 'FINISHED' OR e.physical_input_bytes > 0)
    )
    WHERE catalog_name <> 'system' AND schema_name <> 'information_schema'
) AS s
ON t.object_key = s.object_key
WHEN NOT MATCHED THEN
    INSERT (object_key, table_catalog, table_schema, table_name, table_type, in_directory, first_seen, deleted_at)
    VALUES (s.object_key, s.catalog_name, s.schema_name, s.table_name, 'UNKNOWN', false, DATE '${day}', NULL);

-- 3. Deletion: a directory object that is missing from today's snapshot. Skipped if there is no snapshot
--    for the day (then we know nothing), and for objects first seen later than the day (old re-runs).
MERGE INTO iceberg.core.dim_object AS t
USING (
    SELECT d.object_key
    FROM iceberg.core.dim_object d
    WHERE d.in_directory
      AND d.deleted_at IS NULL
      AND d.first_seen < DATE '${day}'
      AND EXISTS (SELECT 1 FROM iceberg.raw.object_snapshot WHERE snapshot_date = DATE '${day}')
      AND NOT EXISTS (
          SELECT 1 FROM iceberg.raw.object_snapshot s
          WHERE s.snapshot_date = DATE '${day}'
            AND from_big_endian_64(xxhash64(to_utf8(s.table_catalog || '.' || s.table_schema || '.' || s.table_name))) = d.object_key
      )
) AS x
ON t.object_key = x.object_key
WHEN MATCHED THEN
    UPDATE SET deleted_at = DATE '${day}'
