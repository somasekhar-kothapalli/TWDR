"""Run: python -m tests.test_vismaya_calendar_backfill   (no network; the HTML mimics Investing.com's occurrence table)."""
from datetime import date, datetime, time, timezone

from app.vismaya import ref_calendar as vc
from app.vismaya import calendar_backfill as vb
from app.vismaya import db as vismaya_db


def page(*rows):
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<html><table data-test="occurrence-table"><tbody>{body}</tbody></table></html>'


CRUDE = page(
    ["21-10-2026", "14:30", "", "", "-8.557M"],                  # not released: only the previous is known
    ["30-09-2026", "14:30", "0.922M", "-0.700M", "2.969M"],
    ["23-09-2026", "14:30", "2.969M", "", "-0.640M"],            # no forecast posted: NULL, never 0
    ["", "", "", "", ""],                                        # a spacer row
    ["16-09-2026", "14:30", "250K", "-1.600M", "-0.391M"],       # thousands
)
SAVE = lambda html, slug, at: ("sha1", f"investing_com/{slug}/x.html", len(html))  # noqa: E731 - no disk in tests
CAPTURED = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def test_parse_table_scales_to_thousand_barrels_and_keeps_blanks_null():
    rows = vb.parse_table(CRUDE, 1000)
    assert [r["release_date"] for r in rows] == [date(2026, 10, 21), date(2026, 9, 30), date(2026, 9, 23), date(2026, 9, 16)]
    new, old, blank, small = rows
    assert (new["actual"], new["forecast"], new["previous"]) == (None, None, -8557.0)
    assert (old["actual"], old["forecast"], old["previous"], old["release_time"]) == (922.0, -700.0, 2969.0, time(14, 30))
    assert blank["forecast"] is None and blank["actual"] == 2969.0
    assert small["actual"] == 250.0


def test_refinery_is_percentage_points_not_scaled():
    row = vb.parse_table(page(["15-10-2026", "16:00", "0.8%", "", "0.2%"]), 1)[0]
    assert (row["actual"], row["forecast"], row["previous"], row["release_time"]) == (0.8, None, 0.2, time(16, 0))


def test_a_page_with_no_table_gives_no_rows():
    assert vb.parse_table("<html>blocked</html>", 1000) == []


def test_drop_monthly_removes_the_monthly_series_but_keeps_isolated_weekly_forecast_rows():
    rows = [{"release_date": d} for d in (date(2013, 6, 5), date(2013, 5, 30), date(2013, 5, 1), date(2013, 4, 1), date(2013, 3, 1))]
    assert [r["release_date"] for r in vb.drop_monthly(rows)] == [date(2013, 6, 5), date(2013, 5, 30)]   # the 1st-of-month rows go
    cushing = [{"release_date": date(2016, 3, 30)}, {"release_date": date(2016, 3, 2)}]   # forecast-only rows, 28 days apart
    assert len(vb.drop_monthly(cushing)) == 2                                              # not the 1st: kept


def test_collect_reports_the_pages_that_failed_and_drops_monthly_distillate_rows():
    got, failed = vb.collect(["eia_crude", "eia_refinery"], lambda slug: CRUDE if "crude" in slug else None)
    assert list(got) == ["eia_crude"] and failed == ["eia_refinery"]
    html = page(["05-06-2013", "14:30", "2.611M", "1.228M", "1.851M"], ["30-05-2013", "14:30", "1.851M", "0.017M", "-1.052M"],
                ["01-05-2013", "14:30", "0.793M", "", "-1.937M"], ["01-04-2013", "14:30", "-1.937M", "", "-2.167M"])
    got, _ = vb.collect(["eia_distillate"], lambda slug: html)
    assert [r["release_date"] for r in got["eia_distillate"][2]] == [date(2013, 6, 5), date(2013, 5, 30)]


def test_load_calendar_builds_wpsr_weeks_from_the_crude_pages_and_registers_the_raw_page():
    con = vismaya_db.connect(":memory:")
    html = page(["21-10-2026", "14:30", "", "", "-8.557M"], ["30-09-2026", "14:30", "0.922M", "-0.700M", "2.969M"],
                ["20-07-2011", "14:30", "1.0M", "2.0M", "3.0M"])            # before the first calendar week: ignored
    got, _ = vb.collect(["eia_crude"], lambda slug: html)
    calendars = vb.load_calendar(con, got, CAPTURED, save=SAVE)
    assert list(calendars) == ["WPSR"]
    assert con.execute("SELECT report_seq, week_ending, holiday_shift FROM ref.calendar ORDER BY 1").fetchall() == [
        (vc.seq_for(date(2026, 9, 25)), date(2026, 9, 25), False), (vc.seq_for(date(2026, 10, 16)), date(2026, 10, 16), False)]
    assert con.execute("SELECT report_type, report_seq, source FROM ref.raw_files").fetchone() == ("WPSR", None, "investing_com")


def test_the_natural_gas_page_builds_the_wngsr_calendar():
    con = vismaya_db.connect(":memory:")
    html = page(["15-10-2026", "14:30", "", "", "53.00B"], ["08-10-2026", "14:30", "58.00B", "54.00B", "64.00B"])
    got, _ = vb.collect(["eia_natural_gas"], lambda slug: html)
    vb.load_calendar(con, got, CAPTURED, save=SAVE)
    assert con.execute("SELECT report_type, week_ending, holiday_shift FROM ref.calendar ORDER BY report_seq DESC").fetchall() == [
        ("WNGSR", date(2026, 10, 9), False), ("WNGSR", date(2026, 10, 2), False)]
    assert con.execute("SELECT report_type FROM ref.raw_files").fetchone() == ("WNGSR",)
    assert con.execute("SELECT count(*) FROM wpsr.forecasts").fetchone()[0] == 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
