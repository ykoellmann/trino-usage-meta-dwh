"""Synthetic raw data with a small, hand-countable set of special cases.

    uv run generator/generate.py          reset the raw tables, load everything except the late event
    uv run generator/generate.py --late   additionally load the event that only ends after the Thursday run

All times are UTC. Mon 2026-10-12 .. Thu 2026-10-22.
"""
import sys
from datetime import date, datetime, timedelta, timezone

import trino

DAYS = [date(2026, 10, d) for d in range(12, 23)]
MISSING_TEAM_SNAPSHOT = {14}  # the team export failed on this day
MISSING_OBJECT_SNAPSHOT = {15}  # the table directory export failed on this day


def at(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


# ---------------------------------------------------------------- objects
IDE = ("iceberg", "analytics", "ide_events")
PLUGINS = ("iceberg", "analytics", "plugins")
IDE_VIEW = ("iceberg", "analytics", "ide_events_v")  # view on ide_events
SUMMARY = ("iceberg", "analytics", "daily_summary")  # written, never read
SCRATCH = ("iceberg", "analytics", "scratch_dedup")  # read and written by the same query
UNUSED = ("iceberg", "analytics", "old_unused")  # never touched
NEW = ("iceberg", "analytics", "new_feature_events")  # appears on Thu, never queried
TMP = ("iceberg", "staging", "tmp_export")  # dropped on Wed
FLASH = ("iceberg", "analytics", "flash_table")  # created and dropped between two snapshots
CRM = ("postgres", "crm", "customers")  # federated, other catalog
INFO = ("iceberg", "information_schema", "tables")  # metadata noise, must be filtered
RUNTIME = ("system", "runtime", "queries")  # metadata noise, must be filtered

# (object, type, first day in the snapshot, last day in the snapshot)
# FLASH and CRM are in no snapshot: the directory only covers the iceberg catalog and runs once a day.
OBJECTS = [
    (IDE, "BASE TABLE", 12, 22),
    (PLUGINS, "BASE TABLE", 12, 22),
    (IDE_VIEW, "VIEW", 12, 22),
    (SUMMARY, "BASE TABLE", 12, 22),
    (SCRATCH, "BASE TABLE", 12, 22),
    (UNUSED, "BASE TABLE", 12, 22),
    (TMP, "BASE TABLE", 12, 20),
    (NEW, "BASE TABLE", 22, 22),
]

# ---------------------------------------------------------------- users and teams
TEAM_NAMES = {"T1": "Analytics", "T2": "Platform", "T3": "BI"}
RENAMES = {"T1": (20, "Product Analytics")}  # team_id -> (first day with the new name, new name)


def team_name(team_id, day):
    renamed_on, new_name = RENAMES.get(team_id, (None, None))
    return new_name if renamed_on and day.day >= renamed_on else TEAM_NAMES[team_id]


# login -> (account_type, [(first day in this team, team_id, changed_at)], last day in the snapshot or None)
# A user is missing from the snapshot before the first entry and after the last day.
USERS = {
    "anna.schmidt": ("human", [(12, "T1", None), (21, "T2", at(21, 8))], None),  # changes team on Wed
    "ben.meyer": ("human", [(12, "T1", None)], None),
    "carl.weber": ("human", [(12, "T2", None)], None),
    "dana.neu": ("human", [(22, "T1", None)], None),  # new hire, first snapshot on Thu
    "erik.gone": ("human", [(12, "T2", None)], 15),  # leaves the snapshot after Thu 15
    "tableau_service": ("service", [(12, "T3", None)], None),
    "airflow_etl": ("service", [(12, "T2", None)], None),
    # bob.unknown queries but is deliberately in no snapshot
}

# ---------------------------------------------------------------- events
REF_T = "ROW(catalog_name varchar, schema_name varchar, table_name varchar, columns array(varchar), directly_referenced boolean)"
IN_T = "ROW(catalog_name varchar, schema_name varchar, table_name varchar, columns array(varchar), physical_input_bytes bigint, physical_input_rows bigint)"
OUT_T = "ROW(catalog_name varchar, schema_name varchar, table_name varchar)"
FAIL_T = "ROW(error_code integer, error_name varchar, error_type varchar)"

# error codes are illustrative
SYNTAX_ERROR = (1, "SYNTAX_ERROR", "USER_ERROR")
MEMORY_LIMIT = (131073, "EXCEEDED_GLOBAL_MEMORY_LIMIT", "INSUFFICIENT_RESOURCES")


def ev(user, source, start, secs, reads=(), *, via=None, writes=None, error=None,
       cpu_s=10.0, mem_gb=1, late=False):
    """reads: [(object, columns, physical_input_bytes)]; via: view the reads went through;
    writes: (object, written_bytes)."""
    return dict(user=user, source=source, start=start, secs=secs, reads=reads, via=via,
                writes=writes, error=error, cpu_s=cpu_s, mem_gb=mem_gb, late=late)


EVENTS = [
    # ---- Mon 12 (previous week, gives the trend queries a second week)
    ev("anna.schmidt", "datagrip", at(12, 10, 0), 6, [(IDE, ["ide", "feature"], 1_500_000_000)], cpu_s=30),
    ev("ben.meyer", "trino-cli", at(12, 11, 0), 3, [(PLUGINS, ["plugin_id"], 40_000_000)], cpu_s=8),
    # ---- Tue 13
    ev("airflow_etl", "airflow", at(13, 2, 0), 50, [(IDE, ["ide", "event_date"], 5_000_000_000)],
       writes=(SUMMARY, 900_000), cpu_s=350, mem_gb=3),
    ev("tableau_service", "tableau", at(13, 12, 0), 3, [(IDE, ["ide"], 400_000_000)], via=IDE_VIEW, cpu_s=15),
    # ---- Wed 14: no team snapshot on this day
    ev("carl.weber", "trino-cli", at(14, 9, 0), 4, [(IDE, ["ide"], 1_000_000_000)], cpu_s=20),
    ev("ben.meyer", "trino-cli", at(14, 10, 0), 2, [(TMP, ["id"], 10_000_000)], cpu_s=3),
    # ---- Thu 15: no table directory snapshot on this day
    ev("anna.schmidt", "datagrip", at(15, 10, 0), 5, [(PLUGINS, ["plugin_id", "plugin_name"], 60_000_000)], cpu_s=12),
    ev("erik.gone", "trino-cli", at(15, 14, 0), 3, [(PLUGINS, ["plugin_id"], 30_000_000)], cpu_s=7),  # last day before leaving
    # ---- Fri 16
    ev("ben.meyer", "trino-cli", at(16, 15, 0), 10, [(SCRATCH, ["id", "ts"], 200_000_000)],
       writes=(SCRATCH, 150_000_000), cpu_s=60),  # reads and writes the same table
    # ---- Mon 19
    ev("anna.schmidt", "datagrip", at(19, 9, 0), 1, [(INFO, ["table_name"], 0)], cpu_s=0.1),  # noise
    ev("anna.schmidt", "datagrip", at(19, 10, 15), 14,
       [(IDE, ["ide", "plugin_id"], 8_000_000_000), (PLUGINS, ["plugin_id", "plugin_name"], 589_934_592)],
       cpu_s=312, mem_gb=2),  # two tables, one cpu value
    ev("anna.schmidt", "datagrip", at(19, 10, 40), 5, [(IDE, ["ide"], 2_000_000_000)], cpu_s=40),
    ev("ben.meyer", "trino-cli", at(19, 11, 0), 8, [(IDE, ["ide", "feature"], 3_000_000_000)], cpu_s=90),
    ev("tableau_service", "tableau", at(19, 12, 0), 3, [(IDE, ["ide"], 500_000_000)], via=IDE_VIEW, cpu_s=20),
    ev("tableau_service", "tableau", at(19, 13, 0), 3, [(IDE, ["ide"], 500_000_000)], via=IDE_VIEW, cpu_s=20),  # same dashboard again
    ev("ben.meyer", "trino-cli", at(19, 14, 0), 1, [], error=SYNTAX_ERROR, cpu_s=0.05),  # reads nothing
    ev("ben.meyer", "trino-cli", at(19, 15, 0), 20,
       [(IDE, ["ide", "user_id"], 4_000_000_000), (CRM, ["user_id", "name"], 100_000_000)], cpu_s=200),  # federation
    ev("bob.unknown", "trino-cli", at(19, 16, 0), 4, [(PLUGINS, ["plugin_id"], 50_000_000)], cpu_s=15),
    ev("carl.weber", "trino-cli", at(19, 16, 30), 2, [(TMP, ["id"], 10_000_000)], cpu_s=5),
    # ---- Tue 20
    ev("airflow_etl", "airflow", at(20, 2, 0), 60, [(IDE, ["ide", "event_date"], 6_000_000_000)],
       writes=(SUMMARY, 1_000_000), cpu_s=400, mem_gb=3),  # write, SUMMARY never read
    ev("ben.meyer", "trino-cli", at(20, 10, 0), 1200, [(IDE, ["ide", "user_id"], 20_000_000_000)],
       error=MEMORY_LIMIT, cpu_s=5000, mem_gb=60),  # failed, but read data and burned resources
    ev("carl.weber", "trino-cli", at(20, 11, 0), 5, [(PLUGINS, ["plugin_id"], 60_000_000)], cpu_s=12),
    ev("anna.schmidt", "datagrip", at(20, 14, 0), 6, [(FLASH, ["id"], 1_000_000)], cpu_s=3),  # object missing in the directory
    ev("carl.weber", "trino-cli", at(20, 15, 0), 2, [(TMP, ["id"], 10_000_000)], cpu_s=4),  # last day of tmp_export
    ev("carl.weber", "trino-cli", at(20, 23, 58), 360, [(IDE, ["ide"], 1_500_000_000)], cpu_s=30),  # ends Wed 00:04
    # ---- Wed 21
    ev("anna.schmidt", "datagrip", at(21, 9, 30), 7, [(IDE, ["ide", "plugin_id"], 2_500_000_000)], cpu_s=55),  # now Platform
    ev("dana.neu", "datagrip", at(21, 10, 0), 3, [(PLUGINS, ["plugin_id"], 40_000_000)], cpu_s=6),  # not in any snapshot yet
    ev("tableau_service", "tableau", at(21, 12, 0), 3, [(IDE, ["ide"], 500_000_000)], via=IDE_VIEW, cpu_s=20),
    ev("ben.meyer", "trino-cli", at(21, 23, 30), 10_800, [(IDE, ["ide", "user_id"], 12_000_000_000)],
       cpu_s=900, mem_gb=8, late=True),  # ends Thu 02:30, after the Thu 02:00 run
    # ---- Thu 22
    ev("tableau_service", "tableau", at(22, 8, 0), 1, [(RUNTIME, ["query_id"], 0)], cpu_s=0.1),  # noise
    ev("anna.schmidt", "datagrip", at(22, 10, 0), 9,
       [(IDE, ["ide"], 3_000_000_000), (PLUGINS, ["plugin_id"], 70_000_000)], cpu_s=120),
    ev("dana.neu", "datagrip", at(22, 11, 0), 4, [(IDE, ["ide"], 1_000_000_000)], cpu_s=25),  # now known: team T1 (Product Analytics)
    ev("bob.unknown", "trino-cli", at(22, 12, 0), 4, [(IDE, ["ide"], 800_000_000)], cpu_s=18),
    ev("ben.meyer", "trino-cli", at(22, 13, 0), 1, [], cpu_s=0.2),  # SELECT 1: no table, still a resource
]


# ---------------------------------------------------------------- SQL rendering
def s(v):
    return "NULL" if v is None else "'" + v.replace("'", "''") + "'"


def ts(d):
    return "NULL" if d is None else f"TIMESTAMP '{d:%Y-%m-%d %H:%M:%S.%f} UTC'"


def big(n):
    return "NULL" if n is None else f"BIGINT '{n}'"


def arr(items, elem_type):
    return f"ARRAY[{', '.join(items)}]" if items else f"CAST(ARRAY[] AS ARRAY({elem_type}))"


def obj(o):
    return ", ".join(s(p) for p in o)


def cols(c):
    return "ARRAY[" + ", ".join(s(x) for x in c) + "]"


def event_row(i, e):
    reads, via = e["reads"], e["via"]
    # a view shows up as directly referenced, the table behind it only indirectly
    refs = [(via, reads[0][1], True)] + [(o, c, False) for o, c, _ in reads] if via else [(o, c, True) for o, c, _ in reads]
    inputs = [f"CAST(ROW({obj(o)}, {cols(c)}, {big(b)}, {big(b // 100)}) AS {IN_T})" for o, c, b in reads]
    refs = [f"CAST(ROW({obj(o)}, {cols(c)}, {str(d).lower()}) AS {REF_T})" for o, c, d in refs]
    start, secs = e["start"], e["secs"]
    queued_ms = 200
    names = ", ".join(".".join(o) for o, _, _ in reads)
    if e["writes"]:
        text = f"INSERT INTO {'.'.join(e['writes'][0])} SELECT ... FROM {names}"
    else:
        text = f"SELECT ... FROM {names}" if reads else "SELECT 1"
    written = e["writes"][1] if e["writes"] else None
    out = f"CAST(ROW({obj(e['writes'][0])}) AS {OUT_T})" if e["writes"] else f"CAST(NULL AS {OUT_T})"
    fail = f"CAST(ROW({e['error'][0]}, {s(e['error'][1])}, {s(e['error'][2])}) AS {FAIL_T})" if e["error"] else f"CAST(NULL AS {FAIL_T})"
    in_bytes = sum(b for _, _, b in reads)
    query_id = f"{start:%Y%m%d_%H%M%S}_{i:05d}_gen"
    state = "FAILED" if e["error"] else "FINISHED"
    result_bytes, result_rows = (0, 0) if written or e["error"] else (1000, 10)
    return (
        f"({s(query_id)}, {s(state)}, {s(text)}, {s(e['user'])}, {s(e['source'])}, "
        f"{big(round(e['cpu_s'] * 1000))}, {big(secs * 1000)}, {big(queued_ms)}, "
        f"DOUBLE '{e['mem_gb'] * 1e9 * secs}', {big(round(e['mem_gb'] * 1e9))}, {big(in_bytes)}, "
        f"{big(result_bytes)}, {big(result_rows)}, "
        f"{big(written)}, {big(None if written is None else written // 100)}, "
        f"{arr(refs, REF_T)}, {arr(inputs, IN_T)}, {out}, {fail}, "
        f"{ts(start)}, {ts(start + timedelta(milliseconds=queued_ms))}, {ts(start + timedelta(seconds=secs))})"
    )


QUERY_COLS = (
    "query_id, query_state, query_text, user_name, source, cpu_time_ms, wall_time_ms, queued_time_ms, "
    "cumulative_memory, peak_user_memory_bytes, physical_input_bytes, output_bytes, output_rows, "
    "written_bytes, written_rows, referenced_tables, inputs, output, failure_info, "
    "create_time, execution_start_time, end_time"
)


def team_rows():
    for day in DAYS:
        if day.day in MISSING_TEAM_SNAPSHOT:
            continue
        for login, (account_type, segments, last_day) in USERS.items():
            current = [seg for seg in segments if seg[0] <= day.day]
            if not current or (last_day and day.day > last_day):
                continue
            first_day, team_id, changed_at = current[-1]
            yield (f"(DATE '{day}', {s(login)}, {s(team_id)}, {s(team_name(team_id, day))}, {s(account_type)}, "
                   f"{ts(changed_at if first_day == day.day else None)})")


def object_rows():
    for day in DAYS:
        if day.day in MISSING_OBJECT_SNAPSHOT:
            continue
        for o, table_type, first, last in OBJECTS:
            if first <= day.day <= last:
                yield f"(DATE '{day}', {obj(o)}, {s(table_type)})"


def main():
    late_only = "--late" in sys.argv
    cur = trino.dbapi.connect(host="localhost", port=8080, user="generator", catalog="iceberg").cursor()

    def run(sql):
        cur.execute(sql)
        cur.fetchall()

    ids = {id(e): i for i, e in enumerate(EVENTS, 1)}  # stable ids, independent of the mode
    if late_only:
        events = [e for e in EVENTS if e["late"]]
        for e in events:
            run(f"DELETE FROM iceberg.raw.query_events WHERE query_id LIKE '%\\_{ids[id(e)]:05d}\\_gen' ESCAPE '\\'")
    else:
        for t in ("query_events", "team_snapshot", "object_snapshot"):
            run(f"DELETE FROM iceberg.raw.{t}")
        events = [e for e in EVENTS if not e["late"]]
        run("INSERT INTO iceberg.raw.team_snapshot VALUES " + ", ".join(team_rows()))
        run("INSERT INTO iceberg.raw.object_snapshot VALUES " + ", ".join(object_rows()))
    run(f"INSERT INTO iceberg.raw.query_events ({QUERY_COLS}) VALUES " + ", ".join(event_row(ids[id(e)], e) for e in events))
    print(f"loaded {len(events)} events" + ("" if late_only else ", team and object snapshots"))


if __name__ == "__main__":
    main()
