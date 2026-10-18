"""Vismaya's ref.calendar, built from the release dates the Investing.com pages show (no hand-kept file).

`app.vismaya.calendar_backfill` scrapes the crude-report pages and the natural gas storage page; the release dates in their
tables define the calendar, one row per week and report type:

    week_ending    the Friday the survey covers: the latest Friday on or before (release date - 5 days). That gives
                   release Wed -> the Friday 5 days earlier, Thu -> 6 days, a holiday-delayed Fri -> 7 days, and
                   Mon 29 Dec 2025 -> Fri 19 Dec (EIA's own "data week ending" for that delayed release).
    report_seq     whole weeks since the week ending 29 Jul 2011, plus 1 (seq 1 = released 3 Aug 2011 for WPSR),
                   the same for both report types, so a week has the same seq in WPSR and WNGSR.
    expected_release_utc   the date and time the page shows (UTC); 10:30 ET when the page has no time yet.
    holiday_shift  released on another weekday than the normal one (WPSR Wednesday, WNGSR Thursday). The holiday's
                   name is not on the page, so holiday_name stays NULL.

Pages are used in priority order (crude first): a week takes the date of the first page that has it. A week no page
lists (investing.com has glitches: a release listed under another date, or twice) is simply absent: missing_weeks()
reports those. actual_release_utc and archive_file_found are for the EIA archive and are never set here.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

FIRST_WEEK = date(2011, 7, 29)
NORMAL_WEEKDAY = {"WPSR": 2, "WNGSR": 3}  # Wednesday, Thursday (date.weekday())
COVID_FIRST, COVID_LAST = date(2020, 3, 1), date(2020, 6, 30)
ET = ZoneInfo("America/New_York")


def week_ending_for(release_date):
    """The Friday the report covers: the latest Friday on or before (release date - 5 days)."""
    d = release_date - timedelta(days=5)
    return d - timedelta(days=(d.weekday() - 4) % 7)


def seq_for(week_ending):
    return (week_ending - FIRST_WEEK).days // 7 + 1


def release_utc(day, at):
    """The release instant (UTC) for a page row: its date and UTC time, or 10:30 ET that day when the time is unknown."""
    if at is not None:
        return datetime.combine(day, at, tzinfo=timezone.utc)
    return datetime.combine(day, time(10, 30), tzinfo=ET).astimezone(timezone.utc)


def build_calendar(report_type, pages):
    """{report_seq: row} for one report type. `pages`: lists of rows ({"release_date", "release_time"}), highest priority
    first. Rows from before the first week are ignored."""
    cal = {}
    for rows in pages:
        for r in rows:
            week = week_ending_for(r["release_date"])
            seq = seq_for(week)
            if seq >= 1 and seq not in cal:
                cal[seq] = {"week_ending": week, "release_date": r["release_date"],
                            "expected_release_utc": release_utc(r["release_date"], r["release_time"]),
                            "holiday_shift": r["release_date"].weekday() != NORMAL_WEEKDAY[report_type],
                            "covid_flag": COVID_FIRST <= week <= COVID_LAST}
    return cal


def missing_weeks(cal):
    """The week-ending Fridays between the first and the last calendar week that no page listed."""
    if not cal:
        return []
    weeks = {row["week_ending"] for row in cal.values()}
    first, last = min(weeks), max(weeks)
    return [first + timedelta(days=7 * k) for k in range((last - first).days // 7 + 1) if first + timedelta(days=7 * k) not in weeks]


def upsert(con, report_type, cal):
    """Write the rows to ref.calendar; a rerun updates the derived columns and leaves the EIA-archive columns alone."""
    for seq, r in cal.items():
        con.execute("""
            INSERT INTO ref.calendar (report_type, report_seq, week_ending, expected_release_utc, holiday_shift, covid_flag)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (report_type, report_seq) DO UPDATE SET
                week_ending = excluded.week_ending, expected_release_utc = excluded.expected_release_utc,
                holiday_shift = excluded.holiday_shift, covid_flag = excluded.covid_flag
        """, [report_type, seq, r["week_ending"], r["expected_release_utc"], r["holiday_shift"], r["covid_flag"]])
