"""Load Vismaya's forecast tables (wpsr.forecasts, wngsr.forecasts) from the Investing.com pages that app.vismaya.calendar_backfill saved. One-off, by hand.

    python -m app.vismaya.forecasts [--indicators eia_crude eia_gasoline ... eia_natural_gas] [--db PATH]

No browser and no network: for each page (the five crude-report pages and the natural gas storage page) it reads the newest
saved copy under raw/ (found through ref.raw_files, so every row keeps the sha256 and the download time of the page it came
from), parses every row, and matches it to its ref.calendar week by release date. Crude goes to wpsr.forecasts; natural gas
(Bcf, the lower 48 net change) to wngsr.forecasts. Run the calendar backfill first: it scrapes the pages and builds the
calendar. Values are stored in the report's own unit (thousand barrels; refinery in percentage points; Bcf); a blank
forecast is NULL, never 0. A page already loaded (same sha256) is skipped.
"""
import argparse
import logging

from app.scraper import sources
from app.utils.common import RAW_DIR, VISMAYA_DB_FILE, setup_logging
from app.vismaya import db
from app.vismaya.calendar_backfill import PAGES, SOURCE, SOURCE_TZ, page_rows
from app.vismaya.ref_calendar import seq_for, week_ending_for

logger = logging.getLogger("twdr.vismaya_forecasts")
INSERT = {  # report type -> the forecast table's insert, in its column order
    "WPSR": "INSERT INTO wpsr.forecasts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
    "WNGSR": "INSERT INTO wngsr.forecasts VALUES (?,'lower48',?,?,?,?,?,?,?,?,?,?,?,?)",
}


def latest_page(con, slug, raw_dir=RAW_DIR):
    """(sha256, downloaded_at_utc, html) of the newest saved copy of a page, or None."""
    row = con.execute("SELECT sha256, raw_file, downloaded_at_utc FROM ref.raw_files WHERE source = ? AND url LIKE ? "
                      "ORDER BY downloaded_at_utc DESC LIMIT 1", [SOURCE, "%/" + slug]).fetchone()
    if row is None:
        return None
    return row[0], row[2], (raw_dir / row[1]).read_text(encoding="utf-8")


def calendar_dates(con, report_type):
    """{report_seq: release date (UTC)} of a report type's calendar."""
    return dict(con.execute("SELECT report_seq, CAST(expected_release_utc AT TIME ZONE 'UTC' AS DATE) FROM ref.calendar "
                            "WHERE report_type = ?", [report_type]).fetchall())


def load_forecasts(con, indicators, raw_dir=RAW_DIR):
    """Insert the forecast rows. Returns (inserted, unmatched, duplicates, skipped, missing): rows with no calendar week
    (before the first week), rows dropped because another row of the same page took the same week (the date equal to the
    calendar's wins, then the row with a forecast: the page has glitches such as two rows dated 15 Nov 2023), pages already
    loaded, and pages not saved yet."""
    cals = {}
    for indicator in indicators:
        report_type = PAGES[indicator][0]
        if report_type not in cals:
            cals[report_type] = calendar_dates(con, report_type)
            if not cals[report_type]:
                raise RuntimeError(f"ref.calendar has no {report_type} weeks: run app.vismaya.calendar_backfill first")
    inserted = unmatched = duplicates = 0
    skipped, missing = [], []
    for indicator in indicators:
        report_type, field, unit, _ = PAGES[indicator]
        cal = cals[report_type]
        table = "wpsr.forecasts" if report_type == "WPSR" else "wngsr.forecasts"
        slug = sources.slug_for(indicator, "investing")
        page = latest_page(con, slug, raw_dir)
        if page is None:
            missing.append(indicator)
            continue
        sha, downloaded, html = page
        if con.execute(f"SELECT count(*) FROM {table} WHERE raw_sha256 = ?", [sha]).fetchone()[0]:
            skipped.append(indicator)
            continue
        best = {}
        for r in page_rows(indicator, html):
            seq = seq_for(week_ending_for(r["release_date"]))
            if seq not in cal:
                unmatched += 1
                continue
            key = (abs((r["release_date"] - cal[seq]).days), r["forecast"] is None)
            if seq in best:
                duplicates += 1
            if seq not in best or key < best[seq][0]:
                best[seq] = (key, r)
        for seq, (_, r) in best.items():
            con.execute(INSERT[report_type],
                        [seq, field, SOURCE, slug, r["release_date"], r["release_time"], SOURCE_TZ,
                         r["actual"], r["forecast"], r["previous"], unit, downloaded, sha])
            inserted += 1
    return inserted, unmatched, duplicates, skipped, missing


def main(argv=None):
    setup_logging()
    parser = argparse.ArgumentParser(description="Load the forecast tables from the saved Investing.com pages")
    parser.add_argument("--indicators", nargs="+", choices=list(PAGES), default=list(PAGES))
    parser.add_argument("--db", default=str(VISMAYA_DB_FILE))
    args = parser.parse_args(argv)
    con = run_id = None
    try:
        con = db.connect(args.db)
        run_id = db.start_run(con, "app.vismaya.forecasts")
        inserted, unmatched, duplicates, skipped, missing = load_forecasts(con, args.indicators)
        message = (f"{inserted} forecasts inserted, {unmatched} before the first week, {duplicates} duplicates dropped"
                   + (f"; already loaded: {skipped}" if skipped else "") + (f"; no saved page: {missing}" if missing else ""))
        db.finish_run(con, run_id, "failed" if missing else "success", inserted, message)
        con.close()
        logger.info(message)
        return 1 if missing else 0
    except Exception as exc:  # noqa: BLE001 - top-level guard
        logger.exception("app.vismaya.forecasts failed")
        if con is not None and run_id is not None:
            db.finish_run(con, run_id, "failed", None, f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
