CREATE SCHEMA IF NOT EXISTS iceberg.raw;
CREATE SCHEMA IF NOT EXISTS iceberg.core;
CREATE SCHEMA IF NOT EXISTS iceberg.mart;

CREATE TABLE IF NOT EXISTS iceberg.raw.query_events
(
    query_id                varchar,
    query_state             varchar,
    query_text              varchar,
    user_name               varchar,
    source                  varchar,

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

    referenced_tables       array(row(
        catalog_name            varchar,
        schema_name             varchar,
        table_name              varchar,
        columns                 array(varchar),
        directly_referenced     boolean
    )),
    inputs                  array(row(
        catalog_name            varchar,
        schema_name             varchar,
        table_name              varchar,
        columns                 array(varchar),
        physical_input_bytes    bigint,
        physical_input_rows     bigint
    )),
    output                  row(
        catalog_name            varchar,
        schema_name             varchar,
        table_name              varchar
    ),
    failure_info            row(
        error_code              integer,
        error_name              varchar,
        error_type              varchar
    ),

    create_time             timestamp(6) with time zone,
    execution_start_time    timestamp(6) with time zone,
    end_time                timestamp(6) with time zone
)
WITH (
    partitioning = ARRAY['day(create_time)']
);

CREATE TABLE IF NOT EXISTS iceberg.raw.team_snapshot
(
    snapshot_date           date,
    user_login              varchar,
    team_id                 varchar,
    team_name               varchar,
    account_type            varchar,
    changed_at              timestamp(6) with time zone
)
WITH (
    partitioning = ARRAY['snapshot_date']
);

CREATE TABLE IF NOT EXISTS iceberg.raw.object_snapshot
(
    snapshot_date           date,
    table_catalog           varchar,
    table_schema            varchar,
    table_name              varchar,
    table_type              varchar
)
WITH (
    partitioning = ARRAY['snapshot_date']
);
