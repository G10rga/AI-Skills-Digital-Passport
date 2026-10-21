"""Copy an existing SQLite passport DB into PostgreSQL (idempotent).

Usage on the server:
    DATABASE_URL=postgresql://aipassport:PASS@127.0.0.1:5432/aipassport \
    /opt/aipassport/.venv/bin/python backend/tools/migrate_sqlite_to_postgres.py \
        /opt/aipassport/backend/data/passports.db

Existing rows in Postgres are left untouched (ON CONFLICT DO NOTHING),
so re-running is safe. Version ids are preserved. Nothing is deleted
from the SQLite file — it stays as your backup/rollback.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.store import Store  # noqa: E402

TABLES = ["passports", "versions", "version_skills", "records"]


def main() -> None:
    if len(sys.argv) != 2 or not os.getenv("DATABASE_URL", "").startswith("postgres"):
        raise SystemExit(__doc__)
    src_path = Path(sys.argv[1])
    src = sqlite3.connect(src_path)
    src.row_factory = sqlite3.Row
    dst = Store(database_url=os.environ["DATABASE_URL"])
    assert dst.kind == "postgres"

    for table in TABLES:
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        sql = (f"INSERT INTO {table}({','.join(cols)}) "
               f"VALUES ({','.join('%s' for _ in cols)}) ON CONFLICT DO NOTHING")
        cur = dst.db.cursor()
        for row in rows:
            cur.execute(sql, tuple(row[c] for c in cols))
        dst.db.commit()
        count = dst._one(f"SELECT COUNT(*) c FROM {table}")["c"]
        print(f"{table}: {count} rows in postgres ({len(rows)} in sqlite)")
    print("Migration done. Keep the SQLite file as a backup.")


if __name__ == "__main__":
    main()
