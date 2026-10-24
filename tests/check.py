"""End-to-end check against the running stack: expected results, the late event and idempotency.

    uv run tests/check.py

Drops and recreates the core and mart tables and regenerates the raw data. The expected values are counted
by hand from generator/generate.py.
"""
import subprocess
import sys
from pathlib import Path

import trino

ROOT = Path(__file__).parent.parent
cur = trino.dbapi.connect(host="localhost", port=8080, user="check", catalog="iceberg").cursor()
failures = []


def q(sql):
    cur.execute(sql)
    return cur.fetchall()


def step(*args):
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def check(name, actual, expected):
    ok = actual == expected
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n      expected {expected}\n      actual   {actual}"))
    if not ok:
        failures.append(name)


def cpu_and_queries_per_team():
    return dict((name, (cpu, n)) for name, cpu, n in q("""
        SELECT u.team_name, sum(a.cpu_time_ms), sum(a.query_count)
        FROM iceberg.mart.agg_user_resources_daily a
        JOIN iceberg.core.dim_user u ON u.user_key = a.user_key
        GROUP BY 1"""))


def fingerprint():
    tables = {
        "core.dim_user": "user_key, user_login, team_id, team_name, account_type, valid_from, valid_to",
        "core.dim_object": "object_key, table_catalog, table_schema, table_name, table_type, in_directory, first_seen, deleted_at",
        "core.fact_query": "query_id, query_date, user_key, query_state, error_category, sql_hash, cpu_time_ms, cumulative_memory, physical_input_bytes",
        "core.fact_object_access": "query_id, query_date, user_key, object_key, access_type, is_direct, columns_read, physical_input_bytes, written_bytes",
        "mart.agg_user_resources_daily": "query_date, user_key, query_count, cpu_time_ms, cumulative_memory, physical_input_bytes, queued_time_ms, max_peak_user_memory_bytes",
        "mart.agg_object_user_daily": "query_date, object_key, user_key, access_type, is_direct, query_count, physical_input_bytes, written_bytes",
    }
    return {t: q(f"SELECT count(*), checksum(ROW({cols})) FROM iceberg.{t}")[0] for t, cols in tables.items()}


# ---------------------------------------------------------------- fresh state, backfill
for t in ("core.dim_user", "core.dim_object", "core.fact_query", "core.fact_object_access",
          "mart.agg_user_resources_daily", "mart.agg_object_user_daily"):
    q(f"DROP TABLE IF EXISTS iceberg.{t}")
step("run.py", "--init")
step("generator/generate.py")
step("run.py", "2026-10-12", "2026-10-22")

check("B before the late event: cpu_ms and queries per team", cpu_and_queries_per_team(), {
    "Product Analytics": (5_783_250, 14), "Platform": (1_003_000, 10), "BI": (75_000, 4), "Unknown": (39_000, 3)})

# ---------------------------------------------------------------- late event, daily run with lookback
step("generator/generate.py", "--late")
step("run.py", "2026-10-21", "2026-10-22")

check("B after the late event: cpu_ms and queries per team", cpu_and_queries_per_team(), {
    "Product Analytics": (6_683_250, 15), "Platform": (1_003_000, 10), "BI": (75_000, 4), "Unknown": (39_000, 3)})

check("A: distinct users per object (reads)", dict(q("""
    SELECT o.table_name, count(DISTINCT u.user_login)
    FROM iceberg.mart.agg_object_user_daily a
    JOIN iceberg.core.dim_user u ON u.user_key = a.user_key
    JOIN iceberg.core.dim_object o ON o.object_key = a.object_key
    WHERE a.access_type = 'READ'
    GROUP BY 1""")), {
    "ide_events": 7, "ide_events_v": 1, "plugins": 6, "tmp_export": 2, "scratch_dedup": 1, "flash_table": 1, "customers": 1})

check("A: counting user_key instead of login overcounts (team change)", q("""
    SELECT count(DISTINCT u.user_login), count(DISTINCT a.user_key)
    FROM iceberg.mart.agg_object_user_daily a
    JOIN iceberg.core.dim_user u ON u.user_key = a.user_key
    JOIN iceberg.core.dim_object o ON o.object_key = a.object_key
    WHERE a.access_type = 'READ' AND o.table_name = 'ide_events'""")[0], [7, 8])

check("dim_user: team versions and type 1 rename", q("""
    SELECT user_login, team_name, CAST(valid_from AS varchar), CAST(valid_to AS varchar)
    FROM iceberg.core.dim_user
    WHERE user_login IN ('anna.schmidt', 'dana.neu', 'erik.gone', 'bob.unknown')
    ORDER BY 1, 3"""), [
    ["anna.schmidt", "Product Analytics", "2026-10-12", "2026-10-21"],
    ["anna.schmidt", "Platform", "2026-10-21", "9999-12-31"],
    ["bob.unknown", "Unknown", "2026-10-19", "9999-12-31"],
    ["dana.neu", "Unknown", "2026-10-21", "2026-10-22"],
    ["dana.neu", "Product Analytics", "2026-10-22", "9999-12-31"],
    ["erik.gone", "Platform", "2026-10-12", "9999-12-31"]])

check("dim_object: lifecycle", q("""
    SELECT table_name, table_type, in_directory, CAST(first_seen AS varchar), CAST(deleted_at AS varchar)
    FROM iceberg.core.dim_object
    WHERE table_name IN ('tmp_export', 'flash_table', 'customers', 'new_feature_events')
    ORDER BY 1"""), [
    ["customers", "UNKNOWN", False, "2026-10-19", None],
    ["flash_table", "UNKNOWN", False, "2026-10-20", None],
    ["new_feature_events", "BASE TABLE", True, "2026-10-22", None],
    ["tmp_export", "BASE TABLE", True, "2026-10-12", "2026-10-21"]])

check("facts: no missing keys", q("""
    SELECT (SELECT count_if(user_key IS NULL) FROM iceberg.core.fact_query),
           (SELECT count_if(user_key IS NULL OR object_key IS NULL) FROM iceberg.core.fact_object_access)""")[0], [0, 0])

check("facts: metadata-only queries are dropped", q("SELECT count(*) FROM iceberg.core.fact_query")[0][0], 32)

check("mart matches core: cpu and bytes", q("""
    SELECT (SELECT sum(cpu_time_ms) FROM iceberg.core.fact_query) = (SELECT sum(cpu_time_ms) FROM iceberg.mart.agg_user_resources_daily),
           (SELECT sum(physical_input_bytes) FROM iceberg.core.fact_object_access) = (SELECT sum(physical_input_bytes) FROM iceberg.mart.agg_object_user_daily)""")[0],
      [True, True])

for name, query, expected in [
    ("unused tables", "s2_unused_tables.sql", [["analytics", "old_unused", "BASE TABLE"]]),
    ("written but never read", "s2_written_never_read.sql", [["analytics", "daily_summary"]]),
]:
    rows = q((ROOT / "sql/queries" / query).read_text())
    check(f"example query: {name}", [r[:len(expected[0])] for r in rows], expected)

# ---------------------------------------------------------------- idempotency
before = fingerprint()
step("run.py", "2026-10-21", "2026-10-22")
check("idempotent: the daily run again changes nothing", fingerprint(), before)
step("run.py", "2026-10-12", "2026-10-22")
check("idempotent: the whole backfill again changes nothing", fingerprint(), before)

print(f"\n{len(failures)} failed" if failures else "\nall checks passed")
sys.exit(1 if failures else 0)
