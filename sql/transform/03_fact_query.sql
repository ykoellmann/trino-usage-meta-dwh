-- fact_query for one day (${day}, a UTC day of create_time): replace the whole partition.
-- Queries that only read system / information_schema are left out. Queries without any table
-- (SELECT 1) stay, they still used resources.
DELETE FROM iceberg.core.fact_query WHERE query_date = DATE '${day}';

INSERT INTO iceberg.core.fact_query
SELECT
    e.query_id,
    DATE '${day}',
    u.user_key,
    e.query_state,
    e.failure_info.error_type,
    e.failure_info.error_name,
    e.source,
    to_hex(sha256(to_utf8(e.query_text))),
    e.cpu_time_ms,
    e.wall_time_ms,
    e.queued_time_ms,
    e.cumulative_memory,
    e.peak_user_memory_bytes,
    e.physical_input_bytes,
    e.output_bytes,
    e.output_rows,
    e.written_bytes,
    e.written_rows,
    e.create_time,
    e.execution_start_time,
    e.end_time
FROM iceberg.raw.query_events e
LEFT JOIN iceberg.core.dim_user u
  ON u.user_login = e.user_name
 AND DATE '${day}' >= u.valid_from
 AND DATE '${day}' < u.valid_to
WHERE e.create_time >= TIMESTAMP '${day} 00:00:00 UTC'
  AND e.create_time < TIMESTAMP '${day} 00:00:00 UTC' + INTERVAL '1' DAY
  AND NOT (
      coalesce(cardinality(e.referenced_tables), 0) > 0
      AND all_match(e.referenced_tables, t -> t.catalog_name = 'system' OR t.schema_name = 'information_schema')
  )
