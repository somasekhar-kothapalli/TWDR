"""Seed Vismaya's ref.calendar (WPSR rows) from data/wpsr_expected_calendar_2011_2026.csv.

    python -m app.vismaya_calendar [--csv PATH] [--db PATH]

One row per expected weekly petroleum release: report_seq, the week it surveys, the expected release instant (UTC),
and the holiday shift. These are EXPECTED times (10:30 ET, a holiday-shifted release is moved a day but its hour is
not adjusted), so a release EIA delayed to 11:00 or 12:00 ET differs by an hour or two; actual_release_utc and
archive_file_found stay NULL here and are filled only from the EIA archive. covid_flag marks the weeks ending
1 Mar to 30 Jun 2020. Rerunning updates the expected columns and leaves the archive columns alone.
"""
import argparse
import logging

from app import vismaya_db
from app.utils.common import DATA_DIR, VISMAYA_DB_FILE, setup_logging

logger = logging.getLogger("twdr.vismaya_calendar")
CSV_FILE = DATA_DIR / "wpsr_expected_calendar_2011_2026.csv"
COVID_FIRST, COVID_LAST = "2020-03-01", "2020-06-30"


def seed(con, csv_path=CSV_FILE):
    """Upsert the WPSR calendar rows; returns the number of rows in the file."""
    n = con.execute("SELECT count(*) FROM read_csv(?, header = true)", [str(csv_path)]).fetchone()[0]
    con.execute("""
        INSERT INTO ref.calendar (report_type, report_seq, week_ending, expected_release_utc, holiday_shift,
                                  holiday_name, covid_flag, notes)
        SELECT 'WPSR', report_seq, CAST(week_ending AS DATE), CAST(release_time_utc || ':00+00' AS TIMESTAMPTZ),
               holiday_shift = 1, NULLIF(holiday_name, ''),
               CAST(week_ending AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE), NULLIF(notes, '')
        FROM read_csv(?, header = true, all_varchar = true)
        ON CONFLICT (report_type, report_seq) DO UPDATE SET
            week_ending = excluded.week_ending, expected_release_utc = excluded.expected_release_utc,
            holiday_shift = excluded.holiday_shift, holiday_name = excluded.holiday_name,
            covid_flag = excluded.covid_flag, notes = excluded.notes
    """, [COVID_FIRST, COVID_LAST, str(csv_path)])
    return n


def main(argv=None):
    setup_logging()
    parser = argparse.ArgumentParser(description="Seed ref.calendar (WPSR) from the expected-release CSV")
    parser.add_argument("--csv", default=str(CSV_FILE))
    parser.add_argument("--db", default=str(VISMAYA_DB_FILE))
    args = parser.parse_args(argv)
    con = vismaya_db.connect(args.db)
    n = seed(con, args.csv)
    first, last, shifted, covid = con.execute(
        "SELECT min(week_ending), max(week_ending), count(*) FILTER (holiday_shift), count(*) FILTER (covid_flag) "
        "FROM ref.calendar WHERE report_type = 'WPSR'").fetchone()
    logger.info("ref.calendar WPSR: %d rows from the file, weeks %s to %s, %d holiday-shifted, %d covid-flagged",
                n, first, last, shifted, covid)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
