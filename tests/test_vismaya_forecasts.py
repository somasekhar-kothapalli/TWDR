"""Run: python -m tests.test_vismaya_forecasts   (no network; the HTML mimics Investing.com's occurrence table)."""
from datetime import date, datetime, time, timezone

from app import vismaya_db
from app import vismaya_forecasts as vf


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


def test_parse_table_scales_to_thousand_barrels_and_keeps_blanks_null():
    rows = vf.parse_table(CRUDE, 1000)
    assert [r["release_date"] for r in rows] == [date(2026, 10, 21), date(2026, 9, 30), date(2026, 9, 23), date(2026, 9, 16)]
    new, old, blank, small = rows
    assert (new["actual"], new["forecast"], new["previous"]) == (None, None, -8557.0)
    assert (old["actual"], old["forecast"], old["previous"], old["release_time"]) == (922.0, -700.0, 2969.0, time(14, 30))
    assert blank["forecast"] is None and blank["actual"] == 2969.0
    assert small["actual"] == 250.0


def test_refinery_is_percentage_points_not_scaled():
    row = vf.parse_table(page(["15-10-2026", "16:00", "0.8%", "", "0.2%"]), 1)[0]
    assert (row["actual"], row["forecast"], row["previous"], row["release_time"]) == (0.8, None, 0.2, time(16, 0))


def test_a_page_with_no_table_gives_no_rows():
    assert vf.parse_table("<html>blocked</html>", 1000) == []


def test_match_seq_takes_the_closest_release_date_within_two_days():
    cal = [(1, datetime(2026, 9, 30, 14, 30, tzinfo=timezone.utc)), (2, datetime(2026, 10, 7, 14, 30, tzinfo=timezone.utc))]
    assert vf.match_seq(cal, date(2026, 9, 30)) == (1, 0)
    assert vf.match_seq(cal, date(2026, 10, 8)) == (2, 1)              # a holiday-delayed release, a day late
    assert vf.match_seq(cal, date(2026, 10, 20)) == (None, None)
    assert vf.match_seq([], date(2026, 9, 30)) == (None, None)


def test_drop_monthly_removes_the_monthly_series_but_keeps_isolated_weekly_forecast_rows():
    rows = [{"release_date": d} for d in (date(2013, 6, 5), date(2013, 5, 30), date(2013, 5, 1), date(2013, 4, 1), date(2013, 3, 1))]
    kept = [r["release_date"] for r in vf.drop_monthly(rows)]
    assert kept == [date(2013, 6, 5), date(2013, 5, 30)]               # the 1st-of-month rows go
    cushing = [{"release_date": date(2016, 3, 30)}, {"release_date": date(2016, 3, 2)}]   # forecast-only rows, 28 days apart
    assert len(vf.drop_monthly(cushing)) == 2                           # not the 1st: kept


def test_collect_reports_the_pages_that_failed():
    got, failed = vf.collect(["eia_crude", "eia_refinery"], lambda slug: CRUDE if "crude" in slug else None)
    assert list(got) == ["eia_crude"] and failed == ["eia_refinery"]


def test_load_writes_raw_registry_and_matched_rows_only():
    con = vismaya_db.connect(":memory:")
    con.execute("INSERT INTO ref.calendar VALUES ('WPSR',1,'2026-09-25','2026-09-30 14:30:00+00',false,null,null,null,false,null)")
    got, _ = vf.collect(["eia_crude"], lambda slug: CRUDE)
    captured = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    inserted, unmatched, duplicates = vf.load(con, got, captured, save=lambda html, slug, at: ("sha1", f"investing_com/{slug}/x.html", len(html)))
    assert (inserted, unmatched, duplicates) == (1, 3, 0)                    # only 30 Sep has a calendar row
    row = con.execute("SELECT report_seq, field, source, actual, forecast, previous, unit, raw_sha256, source_tz FROM wpsr.forecasts").fetchone()
    assert row == (1, "crude_stocks_change", "investing_com", 922.0, -700.0, 2969.0, "thousand_barrels", "sha1", "UTC")
    assert con.execute("SELECT report_type, report_seq FROM ref.raw_files").fetchone() == ("WPSR", None)
    orphans = dict(con.execute("SELECT * FROM meta.v_orphans").fetchall())
    assert orphans["wpsr.forecasts without calendar"] == 0 and orphans["wpsr.forecasts with unknown raw file"] == 0
    later = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)                # a rerun with an identical page
    vf.load(con, got, later, save=lambda html, slug, at: ("sha1", f"investing_com/{slug}/x.html", len(html)))
    assert con.execute("SELECT count(*) FROM ref.raw_files").fetchone()[0] == 1       # one raw file, registered once
    assert con.execute("SELECT count(*) FROM wpsr.forecasts").fetchone()[0] == 2      # but a second capture of the forecast


def test_two_rows_for_one_report_keep_the_one_with_a_forecast():
    con = vismaya_db.connect(":memory:")
    con.execute("INSERT INTO ref.calendar VALUES ('WPSR',1,'2023-11-10','2023-11-15 15:30:00+00',false,null,null,null,false,null)")
    rows = [{"release_date": date(2023, 11, 15), "release_time": None, "actual": 3600.0, "forecast": 1793.0, "previous": 13869.0},
            {"release_date": date(2023, 11, 15), "release_time": None, "actual": 13869.0, "forecast": None, "previous": 774.0}]  # a glitch on the page
    got = {"eia_crude": ("slug", "txt", rows)}
    inserted, unmatched, duplicates = vf.load(con, got, datetime(2026, 10, 18, tzinfo=timezone.utc), save=lambda *a: ("shaX", "investing_com/slug/c.html", 1))
    assert (inserted, unmatched, duplicates) == (1, 0, 1)
    assert con.execute("SELECT actual, forecast FROM wpsr.forecasts").fetchone() == (3600.0, 1793.0)


def test_collect_drops_the_monthly_distillate_rows():
    html = page(["05-06-2013", "14:30", "2.611M", "1.228M", "1.851M"], ["30-05-2013", "14:30", "1.851M", "0.017M", "-1.052M"],
                ["01-05-2013", "14:30", "0.793M", "", "-1.937M"], ["01-04-2013", "14:30", "-1.937M", "", "-2.167M"])
    got, _ = vf.collect(["eia_distillate"], lambda slug: html)
    assert [r["release_date"] for r in got["eia_distillate"][2]] == [date(2013, 6, 5), date(2013, 5, 30)]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
