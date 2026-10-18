"""Run: python -m tests.test_vismaya_calendar   (the calendar is built from page rows; in-memory DuckDB)."""
from datetime import date, datetime, time, timezone

from app.vismaya import ref_calendar as vc
from app.vismaya import db as vismaya_db


def rows(*items):
    return [{"release_date": d, "release_time": t} for d, t in items]


def test_week_ending_is_the_friday_the_report_covers():
    assert vc.week_ending_for(date(2011, 8, 3)) == date(2011, 7, 29)        # Wednesday release: 5 days after
    assert vc.week_ending_for(date(2026, 10, 15)) == date(2026, 10, 9)      # Thursday (holiday-delayed): 6 days
    assert vc.week_ending_for(date(2013, 12, 27)) == date(2013, 12, 20)     # Friday (Christmas): 7 days
    assert vc.week_ending_for(date(2025, 12, 29)) == date(2025, 12, 19)     # Monday: EIA's "data week ending Dec 19"
    assert vc.week_ending_for(date(2026, 10, 20)) == date(2026, 10, 9)      # a Tuesday is still the week before's report
    assert vc.week_ending_for(date(2026, 10, 21)) == date(2026, 10, 16)


def test_seq_counts_weeks_from_the_first_week():
    assert vc.seq_for(date(2011, 7, 29)) == 1
    assert vc.seq_for(date(2011, 8, 5)) == 2
    assert vc.seq_for(date(2026, 10, 16)) == 795
    assert vc.seq_for(date(2011, 7, 22)) == 0                              # before the first week


def test_build_calendar_takes_the_first_page_that_lists_a_week_and_flags_a_shifted_weekday():
    crude = rows((date(2026, 10, 15), time(16, 0)), (date(2026, 10, 7), time(14, 30)), (date(2011, 7, 20), time(14, 30)))
    gasoline = rows((date(2026, 10, 14), time(14, 30)), (date(2026, 9, 30), None))   # a day off, and a week crude lacks
    cal = vc.build_calendar("WPSR", [crude, gasoline])
    assert sorted(cal) == [vc.seq_for(date(2026, 9, 25)), vc.seq_for(date(2026, 10, 2)), vc.seq_for(date(2026, 10, 9))]   # 2011 row ignored
    shifted = cal[vc.seq_for(date(2026, 10, 9))]
    assert shifted["release_date"] == date(2026, 10, 15) and shifted["holiday_shift"] is True      # crude's date, a Thursday
    assert shifted["expected_release_utc"] == datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)
    normal = cal[vc.seq_for(date(2026, 10, 2))]
    assert normal["holiday_shift"] is False
    no_time = cal[vc.seq_for(date(2026, 9, 25))]                                                    # only gasoline lists it
    assert no_time["expected_release_utc"] == datetime(2026, 9, 30, 14, 30, tzinfo=timezone.utc)      # 10:30 ET (summer)


def test_natural_gas_normal_day_is_thursday_and_winter_time_shifts_the_default_hour():
    cal = vc.build_calendar("WNGSR", [rows((date(2026, 12, 3), None), (date(2026, 12, 2), None))])
    assert len(cal) == 1 and next(iter(cal.values()))["holiday_shift"] is False                   # Thursday is normal for gas
    assert next(iter(cal.values()))["expected_release_utc"] == datetime(2026, 12, 3, 15, 30, tzinfo=timezone.utc)   # EST: 10:30 ET = 15:30 UTC
    wed = vc.build_calendar("WNGSR", [rows((date(2026, 11, 25), None))])                            # Thanksgiving week: Wednesday
    assert next(iter(wed.values()))["holiday_shift"] is True


def test_covid_flag_and_missing_weeks():
    cal = vc.build_calendar("WPSR", [rows((date(2020, 3, 4), None), (date(2020, 3, 11), None), (date(2020, 3, 25), None), (date(2020, 7, 8), None))])
    assert [cal[s]["week_ending"] for s in sorted(cal)] == [date(2020, 2, 28), date(2020, 3, 6), date(2020, 3, 20), date(2020, 7, 3)]
    assert [cal[s]["covid_flag"] for s in sorted(cal)] == [False, True, True, False]               # weeks ending 1 Mar to 30 Jun 2020
    assert vc.missing_weeks(cal)[:2] == [date(2020, 3, 13), date(2020, 3, 27)]


def test_upsert_updates_derived_columns_and_keeps_archive_columns():
    con = vismaya_db.connect(":memory:")
    cal = vc.build_calendar("WPSR", [rows((date(2026, 10, 7), time(14, 30)))])
    vc.upsert(con, "WPSR", cal)
    seq = vc.seq_for(date(2026, 10, 2))
    con.execute("UPDATE ref.calendar SET archive_file_found = true, actual_release_utc = '2026-10-07 14:31:00+00' WHERE report_seq = ?", [seq])
    vc.upsert(con, "WPSR", vc.build_calendar("WPSR", [rows((date(2026, 10, 8), time(16, 0)))]))   # rerun: same week, new date
    assert con.execute("SELECT count(*) FROM ref.calendar").fetchone()[0] == 1
    row = con.execute("SELECT strftime(expected_release_utc AT TIME ZONE 'UTC', '%H:%M'), holiday_shift, archive_file_found FROM ref.calendar").fetchone()
    assert row == ("16:00", True, True)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
