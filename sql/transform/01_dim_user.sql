-- dim_user for one day (${day}). Days must be processed in ascending order.
--
-- 1. SCD 2 on the team: close the open version and add a new one if the team differs from the snapshot.
--    The extra source row with merge_login = NULL never matches, so it is the one that gets inserted.
--    A login that queried but is in no snapshot and has no row yet gets the team 'Unknown'.
MERGE INTO iceberg.core.dim_user AS t
USING (
    WITH src AS (
        SELECT s.user_login, s.team_id, s.team_name, s.account_type
        FROM iceberg.raw.team_snapshot s
        WHERE s.snapshot_date = DATE '${day}'
          AND NOT EXISTS (
              SELECT 1 FROM iceberg.core.dim_user d
              WHERE d.user_login = s.user_login AND d.valid_from > DATE '${day}'
          )
        UNION ALL
        SELECT DISTINCT e.user_name, '-1', 'Unknown', 'unknown'
        FROM iceberg.raw.query_events e
        WHERE e.create_time >= TIMESTAMP '${day} 00:00:00 UTC'
          AND e.create_time < TIMESTAMP '${day} 00:00:00 UTC' + INTERVAL '1' DAY
          AND NOT EXISTS (
              SELECT 1 FROM iceberg.raw.team_snapshot s
              WHERE s.snapshot_date = DATE '${day}' AND s.user_login = e.user_name
          )
          AND NOT EXISTS (SELECT 1 FROM iceberg.core.dim_user d WHERE d.user_login = e.user_name)
    )
    SELECT user_login AS merge_login, user_login, team_id, team_name, account_type
    FROM src
    UNION ALL
    SELECT NULL, s.user_login, s.team_id, s.team_name, s.account_type
    FROM src s
    JOIN iceberg.core.dim_user d
      ON d.user_login = s.user_login AND d.valid_to = DATE '9999-12-31'
    WHERE d.team_id <> s.team_id
) AS s
ON t.user_login = s.merge_login AND t.valid_from <= DATE '${day}' AND t.valid_to > DATE '${day}'
WHEN MATCHED AND t.valid_to = DATE '9999-12-31' AND t.team_id <> s.team_id THEN
    UPDATE SET valid_to = DATE '${day}'
WHEN NOT MATCHED THEN
    INSERT (user_key, user_login, team_id, team_name, account_type, valid_from, valid_to)
    VALUES (
        from_big_endian_64(xxhash64(to_utf8(s.user_login || '|' || CAST(DATE '${day}' AS varchar)))),
        s.user_login, s.team_id, s.team_name, s.account_type, DATE '${day}', DATE '9999-12-31'
    );

-- 2. Type 1: team_name is overwritten on all versions with this team_id. Only the newest snapshot
--    counts, so re-running an older day cannot bring back an old name.
MERGE INTO iceberg.core.dim_user AS t
USING (
    SELECT team_id, max(team_name) AS team_name
    FROM iceberg.raw.team_snapshot
    WHERE snapshot_date = DATE '${day}'
      AND snapshot_date = (SELECT max(snapshot_date) FROM iceberg.raw.team_snapshot)
    GROUP BY team_id
) AS s
ON t.team_id = s.team_id
WHEN MATCHED AND t.team_name <> s.team_name THEN
    UPDATE SET team_name = s.team_name;

-- 3. Type 1: account_type is a correction, not a change, so it is overwritten on all versions.
MERGE INTO iceberg.core.dim_user AS t
USING (
    SELECT user_login, max(account_type) AS account_type
    FROM iceberg.raw.team_snapshot
    WHERE snapshot_date = DATE '${day}'
      AND snapshot_date = (SELECT max(snapshot_date) FROM iceberg.raw.team_snapshot)
    GROUP BY user_login
) AS s
ON t.user_login = s.user_login
WHEN MATCHED AND t.account_type <> s.account_type THEN
    UPDATE SET account_type = s.account_type
