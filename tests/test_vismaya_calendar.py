"""Run: python -m tests.test_vismaya_calendar   (a temp CSV in the real file's layout; in-memory DuckDB)."""
import tempfile
from pathlib import Path

from app import vismaya_calendar as vc
from app import vismaya_db

HEADER = "report_seq,week_ending,expected_release_date,expected_weekday,holiday_shift,holiday_name,release_time_et,release_time_utc,release_time_ist,us_dst,actual_release_date,archive_file_found,notes\n"
ROWS = [
    "1,2020-02-28,2020-03-04,Wed,0,,10:30,2020-03-04 15:30,2020-03-04 21:00,0,,,\n",                          # winter time, just before the covid weeks
    "2,2020-03-06,2020-03-11,Wed,0,,10:30,2020-03-11 14:30,2020-03-11 20:00,1,,,\n",                          # covid week
    "3,2026-10-09,2026-10-15,Thu,1,Columbus Day (2026-10-12),10:30,2026-10-15 14:30,2026-10-15 20:00,1,,,\n",  # holiday shift
]


def seeded(extra=""):
    con = vismaya_db.connect(":memory:")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cal.csv"
        path.write_text(HEADER + "".join(ROWS) + extra, encoding="utf-8")
        n = vc.seed(con, path)
    return con, n


def test_rows_map_to_ref_calendar():
    con, n = seeded()
    assert n == 3
    rows = con.execute("SELECT report_seq, CAST(week_ending AS VARCHAR), strftime(expected_release_utc AT TIME ZONE 'UTC', '%Y-%m-%d %H:%M'), "
                       "holiday_shift, holiday_name, covid_flag, actual_release_utc, archive_file_found FROM ref.calendar ORDER BY 1").fetchall()
    assert rows[0] == (1, "2020-02-28", "2020-03-04 15:30", False, None, False, None, None)
    assert rows[1][5] is True                                   # covid_flag: weeks ending 1 Mar to 30 Jun 2020
    assert rows[2][3:5] == (True, "Columbus Day (2026-10-12)") and rows[2][5] is False


def test_reseeding_updates_expected_columns_and_keeps_archive_columns():
    con, _ = seeded()
    con.execute("UPDATE ref.calendar SET archive_file_found = true, actual_release_utc = '2026-10-15 16:00:00+00' WHERE report_seq = 3")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "cal.csv"
        path.write_text(HEADER + "".join(ROWS) + "4,2026-10-16,2026-10-21,Wed,0,,10:30,2026-10-21 14:30,2026-10-21 20:00,1,,,\n", encoding="utf-8")
        assert vc.seed(con, path) == 4
    assert con.execute("SELECT count(*) FROM ref.calendar").fetchone()[0] == 4
    assert con.execute("SELECT archive_file_found FROM ref.calendar WHERE report_seq = 3").fetchone()[0] is True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
