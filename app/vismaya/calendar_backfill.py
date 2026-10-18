"""Backfill Vismaya's ref.calendar (crude WPSR and natural gas WNGSR) from Investing.com. Run by hand, once, and again only if needed.

    python -m app.vismaya.calendar_backfill [--indicators eia_crude ... eia_natural_gas] [--since 2011-08-01] [--headless] [--dry-run] [--db PATH]

It opens the event pages (the five crude-report pages: crude, gasoline, distillate, Cushing, refinery; and the natural gas
storage page), one browser session per page and 60 s apart (investing.com 403s anything faster, so a full run takes about
8 minutes), clicks the table's "Show More" control (10 older releases per click, about 80 clicks) until the oldest row
reaches --since (default 2011-08-01), keeps every page untouched under raw/ (registered in ref.raw_files, so each value
traces to its download), and builds ref.calendar from the release dates in the tables (rules in app.vismaya.ref_calendar).
The pages are the input of the next step, `python -m app.vismaya.forecasts`, which loads wpsr.forecasts from the saved
pages without opening a browser.

Browser: a visible window of the installed Google Chrome, scraping in a new second tab (the window's first tab stays on
about:blank), with the page's display zone fixed to UTC. Playwright's bundled Chromium does not work for the history:
investing.com's CDN returns 403 to it for scripts and styles, so the page never hydrates and "Show More" does nothing.
With Chrome the expansion runs by itself (checked 18 Oct 2026: 790 crude rows back to 2011, identical to an earlier hand
capture of the same page; release times are in UTC). The distillate page has a monthly series before mid-2013: those
rows are dropped. Cushing and refinery have a forecast only in some weeks: their other rows are kept with a NULL forecast.
"""
import argparse
import hashlib
import logging
import os
import time
from datetime import date, datetime, timezone

from bs4 import BeautifulSoup

from app.scraper import sources
from app.scraper.sites.investing import InvestingCalendarScraper
from app.scraper.utils.calendar import parse_date, to_mb_suffixed
from app.utils.common import RAW_DIR, VISMAYA_DB_FILE, setup_logging
from app.vismaya import db
from app.vismaya.ref_calendar import build_calendar, missing_weeks, upsert

logger = logging.getLogger("twdr.vismaya_calendar_backfill")

SOURCE = "investing_com"
SOURCE_TZ = "UTC"  # the table's time column reads 14:30 for the 10:30 ET release (checked 18 Oct 2026)
HISTORY_FROM = date(2011, 8, 1)  # the first calendar week (seq 1) is released 3 Aug 2011
# indicator -> (report type, canonical field, unit after parsing, factor from the displayed number). The crude pages show
# million barrels ("-8.557M"), the database keeps thousand barrels; refinery utilisation is a weekly change in points;
# the natural gas page shows Bcf ("53.00B"). The order is the calendar's priority: crude first.
PAGES = {
    "eia_crude": ("WPSR", "crude_stocks_change", "thousand_barrels", 1000),
    "eia_gasoline": ("WPSR", "gasoline_stocks_change", "thousand_barrels", 1000),
    "eia_distillate": ("WPSR", "distillate_stocks_change", "thousand_barrels", 1000),
    "eia_cushing": ("WPSR", "cushing_stocks_change", "thousand_barrels", 1000),
    "eia_refinery": ("WPSR", "refinery_util_change", "percentage_points", 1),
    "eia_natural_gas": ("WNGSR", "net_change", "bcf", 1),
}


def parse_table(html, factor):
    """The occurrence table -> [{release_date, release_time, actual, forecast, previous}] (values scaled by `factor`,
    blank = None). Rows with no date, or with no number at all (a release nobody has forecast yet), are skipped."""
    table = BeautifulSoup(html, "html.parser").find("table", {"data-test": "occurrence-table"})
    body = table.find("tbody") if table is not None else None
    out = []
    for tr in (body.find_all("tr") if body is not None else []):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        day = parse_date(cells[0]) if len(cells) >= 5 else None
        if day is None:
            continue
        values = [to_mb_suffixed(c) for c in cells[2:5]]
        if all(v is None for v in values):
            continue
        actual, forecast, previous = (None if v is None else round(v * factor, 6) for v in values)
        try:
            at = datetime.strptime(cells[1], "%H:%M").time()
        except ValueError:
            at = None
        out.append({"release_date": day, "release_time": at, "actual": actual, "forecast": forecast, "previous": previous})
    return out


def drop_monthly(rows):
    """The distillate page's history before mid-2013 is a MONTHLY series dated the 1st of each month: a row dated the
    1st whose neighbours are all more than 20 days away is not a weekly release, so it is dropped."""
    days = sorted(r["release_date"] for r in rows)
    def isolated(d):
        gaps = [min((abs((d - o).days) for o in days if o < d), default=None), min((abs((o - d).days) for o in days if o > d), default=None)]
        return d.day == 1 and all(g is None or g > 20 for g in gaps) and any(g is not None for g in gaps)
    return [r for r in rows if not isolated(r["release_date"])]


def page_rows(indicator, html):
    """The weekly rows of a page as downloaded (the one place that knows each page's quirks)."""
    rows = parse_table(html, PAGES[indicator][3])
    return drop_monthly(rows) if indicator == "eia_distillate" else rows


def save_raw(html, slug, captured):
    """Write the page as downloaded to raw/investing_com/<slug>/<UTC timestamp>.html -> (sha256, path relative to raw/, bytes)."""
    data = html.encode("utf-8")
    rel = f"{SOURCE}/{slug}/{captured:%Y%m%dT%H%M%SZ}.html"
    path = RAW_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), rel, len(data)


def collect(indicators, get_html):
    """({indicator: (slug, html, rows)} for the pages that gave rows, [indicators that did not]).
    `get_html(slug)` returns the page HTML or None."""
    got, failed = {}, []
    for indicator in indicators:
        slug = sources.slug_for(indicator, "investing")
        html = get_html(slug)
        rows = page_rows(indicator, html) if html else []
        if rows:
            got[indicator] = (slug, html, rows)
        else:
            failed.append(indicator)
    return got, failed


def build_calendars(got):
    """{report type: {report_seq: row}} from the pages collected, in PAGES order (crude first)."""
    calendars = {}
    for report_type in ("WPSR", "WNGSR"):
        pages = [got[i][2] for i, p in PAGES.items() if p[0] == report_type and i in got]
        if pages:
            calendars[report_type] = build_calendar(report_type, pages)
    return calendars


def seed_source_fields(con):
    """ref.source_fields: each Investing.com page slug -> canonical field, unit after parsing, scale factor."""
    for indicator, (report_type, field, unit, factor) in PAGES.items():
        slug = sources.INDICATORS[indicator]["investing"]
        con.execute("INSERT INTO ref.source_fields VALUES (?,?,?,?,?,?,TRUE) ON CONFLICT DO NOTHING",
                    [SOURCE, slug, report_type, field, unit, float(factor)])


def load_calendar(con, got, captured, save=save_raw):
    """Keep every page under raw/ (registered in ref.raw_files) and write ref.calendar. Returns the calendars written."""
    calendars = build_calendars(got)
    seed_source_fields(con)
    for report_type, cal in calendars.items():
        upsert(con, report_type, cal)
    for indicator, (slug, html, _) in got.items():
        sha, rel, size = save(html, slug, captured)
        con.execute("INSERT INTO ref.raw_files VALUES (?,?,?,?,?,?,?,?,?,NULL) ON CONFLICT DO NOTHING",
                    [sha, rel, SOURCE, f"{InvestingCalendarScraper.base_url}{slug}", captured, size, "text/html", SOURCE_TZ, PAGES[indicator][0]])
    return calendars


def calendar_summary(calendars):
    """One line per report type: weeks, first and last week ending, off-normal-weekday weeks, weeks no page listed."""
    lines = []
    for report_type, cal in calendars.items():
        weeks = sorted(r["week_ending"] for r in cal.values())
        gaps = missing_weeks(cal)
        lines.append(f"{report_type}: {len(cal)} weeks {weeks[0]} to {weeks[-1]}, {sum(r['holiday_shift'] for r in cal.values())} off the normal weekday, "
                     f"{len(gaps)} weeks no page lists" + (f" ({', '.join(str(g) for g in gaps[:12])}{' ...' if len(gaps) > 12 else ''})" if gaps else ""))
    return lines


def main(argv=None):
    setup_logging()
    parser = argparse.ArgumentParser(description="Backfill Vismaya's ref.calendar (crude and natural gas) from Investing.com")
    parser.add_argument("--indicators", nargs="+", choices=list(PAGES), default=list(PAGES))
    parser.add_argument("--since", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(), default=HISTORY_FROM,
                        help="click Show More on each page until its oldest release is on or before this date (default 2011-08-01)")
    parser.add_argument("--headless", action="store_true", help="run Chrome without a window (default: a visible window)")
    parser.add_argument("--dry-run", action="store_true", help="fetch and print; write nothing")
    parser.add_argument("--db", default=str(VISMAYA_DB_FILE))
    args = parser.parse_args(argv)
    captured = datetime.now(timezone.utc).replace(microsecond=0)

    loaded = []  # slugs fetched so far: the 2nd page and later wait out the site's session gap

    def get_html(slug):
        """One browser session per page, session_gap_s apart: investing.com 403s a second page in one session
        and back-to-back sessions (twpr v0.1 finding)."""
        if loaded:
            time.sleep(InvestingCalendarScraper.session_gap_s)
        loaded.append(slug)
        scraper = InvestingCalendarScraper()
        scraper.show_more_until = args.since
        scraper.browser_channel, scraper.new_tab, scraper.timezone_id = "chrome", True, "UTC"  # real Chrome hydrates the page
        scraper.headless = args.headless
        with scraper:
            page, _ = scraper.fetch_with_soup(slug)
            return scraper.last_html if page else None

    con = run_id = None
    try:
        got, failed = collect(args.indicators, get_html)
        for indicator, (_, _, rows) in got.items():
            logger.info("%s: %d releases, %s to %s, %d with a forecast", indicator, len(rows), rows[-1]["release_date"],
                        rows[0]["release_date"], sum(r["forecast"] is not None for r in rows))
        for line in calendar_summary(build_calendars(got)):
            logger.info("calendar %s", line)
        if failed:
            logger.error("no usable page for: %s", ", ".join(failed))
        if args.dry_run:
            return 1 if failed else 0
        con = db.connect(args.db)
        run_id = db.start_run(con, "app.vismaya.calendar_backfill")
        calendars = load_calendar(con, got, captured)
        message = "calendar " + "; ".join(calendar_summary(calendars)) + (f"; failed: {failed}" if failed else "")
        db.finish_run(con, run_id, "failed" if failed else "success", sum(len(c) for c in calendars.values()), message)
        con.close()
        logger.info(message)
        return 1 if failed else 0
    except Exception as exc:  # noqa: BLE001 - top-level guard
        logger.exception("vismaya.calendar_backfill failed")
        if con is not None and run_id is not None:
            db.finish_run(con, run_id, "failed", None, f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    os._exit(main())  # as the other entry points: a losing browser thread must not hang shutdown
