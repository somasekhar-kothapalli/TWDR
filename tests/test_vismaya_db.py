"""Vismaya schema: applies, is idempotent, and its views compute (in-memory DuckDB, no files)."""
from app import vismaya_db

T = "'2026-10-01 14:30:00+00'"


def seeded():
    con = vismaya_db.connect(":memory:")
    con.execute(f"INSERT INTO ref.calendar VALUES ('WNGSR',1,'2026-09-25',{T},false,null,{T},true,false,null)")
    con.execute("INSERT INTO ref.raw_files(sha256,raw_file,source,downloaded_at_utc) VALUES ('x','a','investing_com','2026-10-01 14:00:00+00')")
    con.execute("INSERT INTO wngsr.values VALUES (1,'lower48','net_change',64,null,null,'bcf',null),(1,'lower48','implied_flow',62,null,null,'bcf',null)")
    for src, forecast in (("investing_com", 63), ("tradingeconomics", 61)):
        con.execute("INSERT INTO wngsr.forecasts VALUES (1,'lower48','net_change',?,'s',null,null,'ET',64,?,60,'bcf','2026-10-01 13:00:00+00','x')", [src, forecast])
    return con


def test_schema_applies_twice_and_creates_every_schema():
    con = vismaya_db.connect(":memory:")
    con.execute(vismaya_db.SCHEMA_FILE.read_text(encoding="utf-8"))  # second run: nothing breaks
    schemas = {r[0] for r in con.execute("SELECT schema_name FROM information_schema.schemata").fetchall()}
    assert {"ref", "wpsr", "wngsr", "market", "meta"} <= schemas
    counts = vismaya_db.table_counts(con)
    assert len(counts) == 17 and not any(counts.values())


def test_surprise_is_the_first_print_minus_the_median_consensus():
    con = seeded()
    row = con.execute("SELECT consensus, n_sources, surprise, implied_flow_first, has_adjustment FROM wngsr.v_surprise").fetchone()
    assert row == (62.0, 2, 2.0, 62.0, False)
    con.execute("INSERT INTO wngsr.adjustments VALUES (1,'salt','revision',2.0,null,null,'x')")
    assert con.execute("SELECT has_adjustment FROM wngsr.v_surprise").fetchone()[0] is True


def test_forecast_quality_and_actual_mismatch():
    con = seeded()
    assert con.execute("SELECT DISTINCT quality FROM wngsr.v_forecast_quality").fetchall() == [("live",)]
    assert con.execute("SELECT count(*) FROM wngsr.v_actual_mismatch").fetchone()[0] == 0
    con.execute("UPDATE wngsr.forecasts SET actual = 65 WHERE source = 'investing_com'")
    assert con.execute("SELECT source, diff FROM wngsr.v_actual_mismatch").fetchall() == [("investing_com", 1.0)]


def test_orphan_checks_catch_unknown_regions_and_fields():
    bad = dict(seeded().execute("SELECT * FROM meta.v_orphans").fetchall())
    assert bad["wngsr.values with unknown region"] == 2 and bad["wngsr.values without calendar"] == 0


def test_shell_runs_statements_lists_tables_and_survives_errors():
    con = seeded()
    lines = iter([".tables", "select 1", "as one;", "select * from nope;", "select count(*) from wngsr.forecasts;", ".quit"])
    out = []
    vismaya_db.run_shell(con, read=lambda prompt: next(lines), write=out.append)
    text = "\n".join(out)
    assert "wngsr.forecasts  (2 rows)" in text and text.count("error:") == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
