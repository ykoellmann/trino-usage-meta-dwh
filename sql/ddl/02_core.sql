-- Versions are half-open: valid_from <= day < valid_to. The open version has valid_to = 9999-12-31.
-- SCD 2 on team_id. team_name and account_type are type 1, overwritten on all versions.
CREATE TABLE IF NOT EXISTS iceberg.core.dim_user
(
    user_key        bigint,
    user_login      varchar,
    team_id         varchar,
    team_name       varchar,
    account_type    varchar,
    valid_from      date,
    valid_to        date
);

-- Lifecycle instead of versions. table_type = 'UNKNOWN' and in_directory = false for objects
-- that only ever showed up in query events.
CREATE TABLE IF NOT EXISTS iceberg.core.dim_object
(
    object_key      bigint,
    table_catalog   varchar,
    table_schema    varchar,
    table_name      varchar,
    table_type      varchar,
    in_directory    boolean,
    first_seen      date,
    deleted_at      date
);

-- One row per query.
CREATE TABLE IF NOT EXISTS iceberg.core.fact_query
(
    query_id                varchar,
    query_date              date,
    user_key                bigint,
    query_state             varchar,
    error_category          varchar,
    error_name              varchar,
    source                  varchar,
    sql_hash                varchar,

    cpu_time_ms             bigint,
    wall_time_ms            bigint,
    queued_time_ms          bigint,
    cumulative_memory       double,
    peak_user_memory_bytes  bigint,
    physical_input_bytes    bigint,
    output_bytes            bigint,
    output_rows             bigint,
    written_bytes           bigint,
    written_rows            bigint,

    create_time             timestamp(6) with time zone,
    execution_start_time    timestamp(6) with time zone,
    end_time                timestamp(6) with time zone
)
WITH (
    partitioning = ARRAY['query_date']
);

-- One row per query x object x access_type x is_direct.
-- physical_input_bytes belongs to the table that was read (a view row carries 0, the table behind it the bytes).
CREATE TABLE IF NOT EXISTS iceberg.core.fact_object_access
(
    query_id                varchar,
    query_date              date,
    user_key                bigint,
    object_key              bigint,
    access_type             varchar,
    is_direct               boolean,
    columns_read            array(varchar),
    physical_input_bytes    bigint,
    written_bytes           bigint
)
WITH (
    partitioning = ARRAY['query_date']
);
