"""Create (or update) the Vismaya DuckDB database from db/vismaya_schema.sql.

    python -m app.vismaya_db            # data/vismaya.duckdb, schema applied, every table's row count printed
    python -m app.vismaya_db --shell    # a read-only SQL prompt on it (end a statement with ;  .tables  .quit)

The schema is idempotent (CREATE ... IF NOT EXISTS, views are replaced), so rerunning is safe. The file holds
derived data only: it must be rebuildable from raw downloads, so it is git-ignored and never edited by hand.
"""
import argparse
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


def run_shell(con, read=input, write=print):
    """A tiny read-only SQL prompt: statements end with ';', '.tables' lists the tables, '.quit' leaves."""
    write(f"Vismaya (read-only). End a statement with ';'. .tables  .quit")
    buffer = ""
    while True:
        try:
            line = read("sql> " if not buffer else "...> ")
        except EOFError:
            return
        if not buffer and line.strip() in (".quit", ".exit"):
            return
        if not buffer and line.strip() == ".tables":
            write("\n".join(f"{name}  ({n} rows)" for name, n in table_counts(con).items()))
            continue
        buffer += line + "\n"
        if not buffer.rstrip().endswith(";"):
            continue
        try:
            con.sql(buffer).show(max_rows=60)
        except Exception as exc:  # noqa: BLE001 - show the error and keep the prompt
            write(f"error: {exc}")
        buffer = ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create/update the Vismaya DuckDB database")
    parser.add_argument("--shell", action="store_true", help="open a read-only SQL prompt instead")
    if parser.parse_args(argv).shell:
        run_shell(duckdb.connect(str(VISMAYA_DB_FILE), read_only=True))
        return 0
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
