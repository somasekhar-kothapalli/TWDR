"""Collect Investing.com "Forecast" values for the EIA weekly petroleum report into Vismaya's wpsr.forecasts.

    python -m app.vismaya_forecasts [--indicators eia_crude eia_gasoline ...] [--dry-run] [--db PATH]

Each run opens the five crude-report event pages (crude, gasoline, distillate, Cushing, refinery), one browser
session per page and 60 s apart (investing.com 403s anything faster, so a full run takes about 5 minutes), keeps every page
untouched under raw/ (registered in ref.raw_files, so each value traces to its download) and parses the 10 most
recent releases each page lists (its "Show more" button does nothing in a headless browser, so history is built
by capturing weekly). Values are stored in the report's own unit (thousand barrels; refinery in percentage points),
a blank forecast is NULL, never 0. A row is inserted only when its release matches a ref.calendar row (the
release within 2 days of the expected one); rows with no match are counted and left out. Natural gas
(wngsr.forecasts) is a later extension: add the ng_storage indicator and a second table.
"""
import argparse
import hashlib
import logging
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from app import vismaya_db
from app.scraper import sources
from app.scraper.sites.investing import InvestingCalendarScraper
from app.scraper.utils.calendar import parse_date, to_mb_suffixed
from app.utils.common import RAW_DIR, ROOT, VISMAYA_DB_FILE, setup_logging

logger = logging.getLogger("twdr.vismaya_forecasts")

SOURCE = "investing_com"
SOURCE_TZ = "UTC"  # the table's time column reads 14:30 for the 10:30 ET release (checked 21 Oct 2026)
MATCH_WINDOW = timedelta(days=2)
# indicator -> (canonical field, unit after parsing, factor from the displayed number): the page shows
# million barrels ("-8.557M"), the database keeps thousand barrels; refinery utilisation is a weekly change in points.
FIELDS = {
    "eia_crude": ("crude_stocks_change", "thousand_barrels", 1000),
    "eia_gasoline": ("gasoline_stocks_change", "thousand_barrels", 1000),
    "eia_distillate": ("distillate_stocks_change", "thousand_barrels", 1000),
    "eia_cushing": ("cushing_stocks_change", "thousand_barrels", 1000),
    "eia_refinery": ("refinery_util_change", "percentage_points", 1),
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


def match_seq(calendar, release_date, release_time):
    """report_seq of the calendar row whose expected release is closest to this release (within MATCH_WINDOW), else None.
    `calendar`: [(report_seq, expected_release_utc)]."""
    when = datetime.combine(release_date, release_time or datetime.min.time(), tzinfo=timezone.utc)
    gap, seq = min(((abs(when - expected), s) for s, expected in calendar), default=(None, None))
    return seq if gap is not None and gap <= MATCH_WINDOW else None


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
        rows = parse_table(html, FIELDS[indicator][2]) if html else []
        if rows:
            got[indicator] = (slug, html, rows)
        else:
            failed.append(indicator)
    return got, failed


def load(con, got, captured, save=save_raw):
    """Write the raw files and the forecast rows. Returns (inserted, unmatched)."""
    calendar = con.execute("SELECT report_seq, expected_release_utc FROM ref.calendar WHERE report_type = 'WPSR'").fetchall()
    inserted = unmatched = 0
    for indicator, (slug, html, rows) in got.items():
        field, unit, _ = FIELDS[indicator]
        sha, rel, size = save(html, slug, captured)
        con.execute("INSERT INTO ref.raw_files VALUES (?,?,?,?,?,?,?,?,'WPSR',NULL) ON CONFLICT DO NOTHING",
                    [sha, rel, SOURCE, f"{InvestingCalendarScraper.base_url}{slug}", captured, size, "text/html", SOURCE_TZ])
        for r in rows:
            seq = match_seq(calendar, r["release_date"], r["release_time"])
            if seq is None:
                unmatched += 1
                continue
            con.execute("INSERT INTO wpsr.forecasts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [seq, field, SOURCE, slug, r["release_date"], r["release_time"], SOURCE_TZ,
                         r["actual"], r["forecast"], r["previous"], unit, captured, sha])
            inserted += 1
    return inserted, unmatched


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def main(argv=None):
    setup_logging()
    parser = argparse.ArgumentParser(description="Collect Investing.com forecasts for the EIA petroleum report into Vismaya")
    parser.add_argument("--indicators", nargs="+", choices=list(FIELDS), default=list(FIELDS))
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
        with InvestingCalendarScraper() as scraper:
            page, _ = scraper.fetch_with_soup(slug)
            return scraper.last_html if page else None

    try:
        got, failed = collect(args.indicators, get_html)
        for indicator, (_, _, rows) in got.items():
            logger.info("%s: %d releases, newest %s (forecast %s)", indicator, len(rows), rows[0]["release_date"], rows[0]["forecast"])
        if failed:
            logger.error("no usable page for: %s", ", ".join(failed))
        if args.dry_run:
            return 1 if failed else 0
        con = vismaya_db.connect(args.db)
        run_id = str(uuid.uuid4())
        con.execute("INSERT INTO meta.pipeline_runs VALUES (?,?,?,?,NULL,'running',NULL,NULL)",
                    [run_id, "app.vismaya_forecasts", git_commit(), captured])
        inserted, unmatched = load(con, got, captured)
        message = f"{inserted} inserted, {unmatched} rows with no ref.calendar match" + (f", failed: {failed}" if failed else "")
        con.execute("UPDATE meta.pipeline_runs SET finished_at_utc = ?, status = ?, rows_loaded = ?, message = ? WHERE run_id = ?",
                    [datetime.now(timezone.utc), "failed" if failed else "success", inserted, message, run_id])
        con.close()
        logger.info(message)
        return 1 if failed else 0
    except Exception:  # noqa: BLE001 - top-level guard
        logger.exception("vismaya_forecasts failed")
        return 1


if __name__ == "__main__":
    os._exit(main())  # as the other entry points: a losing browser thread must not hang shutdown
