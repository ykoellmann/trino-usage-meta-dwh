"""Runs the DDL and then the transformations for every day of a date range, oldest day first.

    uv run run.py                          the last two days (daily run with lookback)
    uv run run.py 2026-10-19 2026-10-22    backfill: the same job over a longer range, both days inclusive

In production an orchestrator such as Airflow would do this.
"""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import trino

SQL = Path(__file__).parent / "sql"


def statements(path, day=None):
    text = path.read_text()
    if day:
        text = text.replace("${day}", day.isoformat())
    for stmt in text.split(";"):
        if any(line.strip() and not line.strip().startswith("--") for line in stmt.splitlines()):
            yield stmt


def main():
    if len(sys.argv) == 3:
        first, last = (date.fromisoformat(a) for a in sys.argv[1:])
    else:
        last = datetime.now(timezone.utc).date() - timedelta(days=1)
        first = last - timedelta(days=1)

    cur = trino.dbapi.connect(host="localhost", port=8080, user="run", catalog="iceberg").cursor()

    def run(sql):
        cur.execute(sql)
        cur.fetchall()

    for ddl in sorted((SQL / "ddl").glob("*.sql")):
        for stmt in statements(ddl):
            run(stmt)

    day = first
    while day <= last:
        for transform in sorted((SQL / "transform").glob("*.sql")):
            for stmt in statements(transform, day):
                run(stmt)
        print(f"loaded {day}")
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
