"""Run: python -m tests.test_vismaya_forecasts   (no network; saved pages are written to a temp folder; in-memory DuckDB)."""
import hashlib
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from app.vismaya import calendar_backfill as vb
from app.vismaya import db as vismaya_db
from app.vismaya import forecasts as vf

DOWNLOADED = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def page(*rows):
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<html><table data-test="occurrence-table"><tbody>{body}</tbody></table></html>'


def saved(tmp, con, html, indicators=("eia_crude",)):
    """Run the calendar backfill's loading step on `html`, writing the page into `tmp` (the stand-in for raw/)."""
    def save(text, slug, at):
        rel = f"investing_com/{slug}/x.html"
        (Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
        (Path(tmp) / rel).write_text(text, encoding="utf-8")
        return hashlib.sha256(text.encode()).hexdigest(), rel, len(text)
    got, _ = vb.collect(list(indicators), lambda slug: html)
    vb.load_calendar(con, got, DOWNLOADED, save=save)


def test_forecasts_are_matched_to_the_calendar_weeks_built_from_the_same_pages():
    html = page(["21-10-2026", "14:30", "", "", "-8.557M"], ["30-09-2026", "14:30", "0.922M", "-0.700M", "2.969M"],
                ["20-07-2011", "14:30", "1.0M", "2.0M", "3.0M"])            # before the first calendar week
    with tempfile.TemporaryDirectory() as tmp:
        con = vismaya_db.connect(":memory:")
        saved(tmp, con, html)
        inserted, unmatched, duplicates, skipped, missing = vf.load_forecasts(con, ["eia_crude"], raw_dir=Path(tmp))
    assert (inserted, unmatched, duplicates, skipped, missing) == (2, 1, 0, [], [])
    row = con.execute("SELECT field, source, actual, forecast, previous, unit, source_tz, captured_at_utc FROM wpsr.forecasts WHERE forecast IS NOT NULL").fetchone()
    assert row[:7] == ("crude_stocks_change", "investing_com", 922.0, -700.0, 2969.0, "thousand_barrels", "UTC")
    assert row[7] == DOWNLOADED                                          # the page's own download time, not the loading time
    orphans = dict(con.execute("SELECT * FROM meta.v_orphans").fetchall())
    assert orphans["wpsr.forecasts without calendar"] == 0 and orphans["wpsr.forecasts with unknown raw file"] == 0


def test_two_rows_for_one_report_keep_the_one_with_a_forecast():
    html = page(["15-11-2023", "14:30", "3.600M", "1.793M", "13.869M"], ["15-11-2023", "14:30", "13.869M", "", "0.774M"])   # a page glitch
    with tempfile.TemporaryDirectory() as tmp:
        con = vismaya_db.connect(":memory:")
        saved(tmp, con, html)
        inserted, unmatched, duplicates, _, _ = vf.load_forecasts(con, ["eia_crude"], raw_dir=Path(tmp))
    assert (inserted, unmatched, duplicates) == (1, 0, 1)
    assert con.execute("SELECT actual, forecast FROM wpsr.forecasts").fetchone() == (3600.0, 1793.0)


def test_a_page_already_loaded_is_skipped_and_a_page_not_saved_is_reported():
    html = page(["30-09-2026", "14:30", "0.922M", "-0.700M", "2.969M"])
    with tempfile.TemporaryDirectory() as tmp:
        con = vismaya_db.connect(":memory:")
        saved(tmp, con, html)
        assert vf.load_forecasts(con, ["eia_crude"], raw_dir=Path(tmp))[0] == 1
        again = vf.load_forecasts(con, ["eia_crude", "eia_gasoline"], raw_dir=Path(tmp))
    assert again == (0, 0, 0, ["eia_crude"], ["eia_gasoline"])
    assert con.execute("SELECT count(*) FROM wpsr.forecasts").fetchone()[0] == 1


def test_an_empty_calendar_is_an_error():
    con = vismaya_db.connect(":memory:")
    try:
        vf.load_forecasts(con, ["eia_crude"])
    except RuntimeError as exc:
        assert "calendar_backfill" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_natural_gas_forecasts_go_to_wngsr_in_bcf_for_the_lower_48():
    html = page(["15-10-2026", "14:30", "", "", "53.00B"], ["08-10-2026", "14:30", "58.00B", "54.00B", "64.00B"],
                ["01-10-2026", "14:30", "64.00B", "", "53.00B"])
    with tempfile.TemporaryDirectory() as tmp:
        con = vismaya_db.connect(":memory:")
        saved(tmp, con, html, indicators=("eia_natural_gas",))
        inserted, unmatched, duplicates, skipped, missing = vf.load_forecasts(con, ["eia_natural_gas"], raw_dir=Path(tmp))
    assert (inserted, unmatched, duplicates, skipped, missing) == (3, 0, 0, [], [])
    assert con.execute("SELECT count(*) FROM wpsr.forecasts").fetchone()[0] == 0
    row = con.execute("SELECT region, field, source, release_date, actual, forecast, previous, unit, captured_at_utc FROM wngsr.forecasts "
                      "WHERE forecast IS NOT NULL").fetchone()
    assert row == ("lower48", "net_change", "investing_com", date(2026, 10, 8), 58.0, 54.0, 64.0, "bcf", DOWNLOADED)
    orphans = dict(con.execute("SELECT * FROM meta.v_orphans").fetchall())
    assert orphans["wngsr.forecasts without calendar"] == 0 and orphans["wngsr.forecasts with unknown raw file"] == 0
    assert con.execute("SELECT count(*) FROM wngsr.v_consensus").fetchone()[0] == 1               # the view reads it: the 8 Oct week


def test_a_failed_run_is_recorded_as_failed_not_left_running():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "v.duckdb")
        assert vf.main(["--db", path]) == 1                              # no calendar yet: the run fails
        con = vismaya_db.connect(path)
        row = con.execute("SELECT script, status, message FROM meta.pipeline_runs").fetchone()
        con.close()
    assert row[:2] == ("app.vismaya.forecasts", "failed") and "calendar_backfill" in row[2]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
