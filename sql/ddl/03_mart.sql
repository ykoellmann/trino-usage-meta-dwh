-- Question B: resources per team. Day x user version, the team comes from dim_user.
CREATE TABLE IF NOT EXISTS iceberg.mart.agg_user_resources_daily
(
    query_date                  date,
    user_key                    bigint,
    query_count                 bigint,
    cpu_time_ms                 bigint,
    cumulative_memory           double,
    physical_input_bytes        bigint,
    queued_time_ms              bigint,
    max_peak_user_memory_bytes  bigint
)
WITH (
    partitioning = ARRAY['query_date']
);

-- Question A: distinct users per table. Keeps the user, so distinct counts stay exact over any period.
CREATE TABLE IF NOT EXISTS iceberg.mart.agg_object_user_daily
(
    query_date              date,
    object_key              bigint,
    user_key                bigint,
    access_type             varchar,
    is_direct               boolean,
    query_count             bigint,
    physical_input_bytes    bigint,
    written_bytes           bigint
)
WITH (
    partitioning = ARRAY['query_date']
);
