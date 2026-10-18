"""Create (or update) the Vismaya DuckDB database from db/vismaya_schema.sql.

    python -m app.vismaya_db            # data/vismaya.duckdb, schema applied, every table's row count printed

The schema is idempotent (CREATE ... IF NOT EXISTS, views are replaced), so rerunning is safe. The file holds
derived data only: it must be rebuildable from raw downloads, so it is git-ignored and never edited by hand.
"""
import logging

import duckdb

from app.utils.common import ROOT, VISMAYA_DB_FILE, setup_logging

logger = logging.getLogger("twdr.vismaya_db")
SCHEMA_FILE = ROOT / "db" / "vismaya_schema.sql"


def connect(path=VISMAYA_DB_FILE):
    """Open the database (':memory:' for tests) with the schema applied."""
    con = duckdb.connect(str(path))
    con.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    return con


def table_counts(con):
    tables = con.execute("SELECT table_schema, table_name FROM information_schema.tables "
                         "WHERE table_type = 'BASE TABLE' ORDER BY 1, 2").fetchall()
    return {f"{s}.{t}": con.execute(f'SELECT count(*) FROM "{s}"."{t}"').fetchone()[0] for s, t in tables}


def main():
    setup_logging()
    VISMAYA_DB_FILE.parent.mkdir(exist_ok=True)
    con = connect()
    for name, n in table_counts(con).items():
        logger.info("%-28s %d rows", name, n)
    bad = [(name, n) for name, n in con.execute("SELECT * FROM meta.v_orphans").fetchall() if n]
    logger.info("integrity checks failing: %s", bad or "none")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
